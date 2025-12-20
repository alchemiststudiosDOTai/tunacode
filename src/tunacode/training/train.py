"""Unsloth fine-tuning script for tool-calling patterns.

This module provides the training pipeline for fine-tuning LLMs on
tunacode's tool-calling patterns using Unsloth with QLoRA.

Usage:
    from tunacode.training.train import train
    from tunacode.training.config import TrainingConfig

    config = TrainingConfig(dataset_path="data/training.jsonl")
    train(config)

Note: This script requires unsloth and its dependencies to be installed.
These are not included in the main tunacode dependencies to avoid conflicts.
Install in a separate environment:
    pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    pip install trl transformers datasets
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from tunacode.training.config import TrainingConfig

if TYPE_CHECKING:
    from datasets import Dataset

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are a helpful coding assistant with access to tools.

Available tools:
{tools}

When you need to use a tool, respond with a function call in JSON format.
After receiving the tool result, provide a helpful response to the user."""


def load_jsonl_dataset(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dictionaries.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of parsed JSON objects.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If any line is invalid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Invalid JSON at line {line_num}: {e.msg}",
                    e.doc,
                    e.pos,
                ) from e
    return records


def convert_to_hf_dataset(records: list[dict]) -> Dataset:
    """Convert ShareGPT records to a HuggingFace Dataset.

    Args:
        records: List of ShareGPT conversation dictionaries.

    Returns:
        HuggingFace Dataset with 'conversations', 'system', and 'tools' columns.
    """
    from datasets import Dataset

    return Dataset.from_list(records)


def load_dataset(config: TrainingConfig) -> Dataset:
    """Load training data from JSONL into HuggingFace Dataset.

    Args:
        config: Training configuration with dataset_path.

    Returns:
        HuggingFace Dataset ready for training.
    """
    logger.info("Loading dataset from %s", config.dataset_path)
    records = load_jsonl_dataset(config.dataset_path)
    logger.info("Loaded %d conversations", len(records))

    dataset = convert_to_hf_dataset(records)
    logger.info("Dataset columns: %s", dataset.column_names)
    return dataset


def setup_model_and_tokenizer(config: TrainingConfig):
    """Load and configure model with Unsloth optimizations.

    Args:
        config: Training configuration.

    Returns:
        Tuple of (model, tokenizer) ready for training.
    """
    from unsloth import FastLanguageModel

    logger.info("Loading model: %s", config.model_name)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.model_name,
        max_seq_length=config.max_seq_length,
        dtype=None,  # Auto-detect dtype
        load_in_4bit=config.load_in_4bit,
    )

    logger.info("Applying LoRA adapters")
    model = FastLanguageModel.get_peft_model(
        model,
        **config.to_lora_args(),
        random_state=config.seed,
    )

    return model, tokenizer


def format_single_conversation(conv_messages: list[dict], system: str | None, tokenizer) -> str:
    """Format a single ShareGPT conversation for training.

    Args:
        conv_messages: List of message dicts with 'from' and 'value' keys.
        system: Optional system prompt.
        tokenizer: HuggingFace tokenizer with chat template.

    Returns:
        Formatted string ready for tokenization.
    """
    messages = []

    if system:
        messages.append({"role": "system", "content": system})

    role_map = {
        "human": "user",
        "gpt": "assistant",
        "function_call": "assistant",
        "observation": "tool",
    }

    for msg in conv_messages:
        role = role_map.get(msg["from"], msg["from"])
        content = msg["value"]

        if msg["from"] == "function_call":
            content = f"<tool_call>\n{content}\n</tool_call>"
        elif msg["from"] == "observation":
            content = f"<tool_response>\n{content}\n</tool_response>"

        messages.append({"role": role, "content": content})

    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )


def formatting_func_auto(examples: dict, tokenizer) -> list[str]:
    """Format ShareGPT conversations for training (handles batched and single).

    Args:
        examples: Dict with 'conversations', 'system' keys.
                  Can be single example or batched (lists of examples).
        tokenizer: HuggingFace tokenizer with chat template.

    Returns:
        List of formatted strings ready for tokenization.
    """
    conversations = examples["conversations"]
    system = examples.get("system")

    # Detect if batched: if conversations is a list of lists
    if conversations and isinstance(conversations[0], list):
        # Batched mode
        systems_list = system if system else [None] * len(conversations)
        results = []
        for conv, sys in zip(conversations, systems_list):
            formatted = format_single_conversation(conv, sys, tokenizer)
            results.append(formatted)
        return results
    else:
        # Single example mode
        formatted = format_single_conversation(conversations, system, tokenizer)
        return [formatted]


def create_trainer(model, tokenizer, dataset: Dataset, config: TrainingConfig):
    """Create the SFTTrainer for fine-tuning.

    Args:
        model: The model with LoRA adapters.
        tokenizer: The tokenizer.
        dataset: HuggingFace Dataset with training data.
        config: Training configuration.

    Returns:
        Configured SFTTrainer ready to train.
    """
    from transformers import TrainingArguments
    from trl import SFTTrainer

    config.output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(**config.to_sft_trainer_args())

    def format_fn(examples: dict) -> list[str]:
        return formatting_func_auto(examples, tokenizer)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        formatting_func=format_fn,
        max_seq_length=config.max_seq_length,
        args=training_args,
    )

    return trainer


def train(config: TrainingConfig) -> Path:
    """Run the full training pipeline.

    Args:
        config: Training configuration.

    Returns:
        Path to the saved model/adapter directory.

    Raises:
        FileNotFoundError: If dataset file doesn't exist.
        ImportError: If unsloth/trl dependencies aren't installed.
    """
    logger.info("Starting training with config: %s", config.model_name)
    logger.info("Output directory: %s", config.output_dir)

    dataset = load_dataset(config)
    model, tokenizer = setup_model_and_tokenizer(config)
    trainer = create_trainer(model, tokenizer, dataset, config)

    logger.info("Starting training...")
    trainer.train()

    adapter_path = config.output_dir / "lora_adapter"
    logger.info("Saving LoRA adapter to %s", adapter_path)
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)

    logger.info("Training complete!")
    return adapter_path


def save_merged_model(config: TrainingConfig, save_16bit: bool = True) -> Path:
    """Load trained adapter and save merged model.

    Args:
        config: Training configuration (uses output_dir for adapter path).
        save_16bit: If True, save in 16-bit precision; otherwise 4-bit.

    Returns:
        Path to the merged model directory.
    """
    from unsloth import FastLanguageModel

    adapter_path = config.output_dir / "lora_adapter"
    merged_path = config.output_dir / "merged_model"

    logger.info("Loading adapter from %s", adapter_path)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(adapter_path),
        max_seq_length=config.max_seq_length,
        dtype=None,
        load_in_4bit=config.load_in_4bit,
    )

    logger.info("Saving merged model to %s", merged_path)
    if save_16bit:
        model.save_pretrained_merged(
            str(merged_path),
            tokenizer,
            save_method="merged_16bit",
        )
    else:
        model.save_pretrained_merged(
            str(merged_path),
            tokenizer,
            save_method="merged_4bit",
        )

    logger.info("Merged model saved!")
    return merged_path


def main():
    """CLI entry point for training."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Fine-tune LLM on tool-calling patterns with Unsloth"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to JSONL training data",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="unsloth/qwen3-4b",
        help="Model name or path (default: unsloth/qwen3-4b)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output"),
        help="Output directory for checkpoints and model (default: ./output)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=1,
        help="Number of training epochs (default: 1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Per-device batch size (default: 2)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=-1,
        help="Maximum training steps (-1 for full dataset)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-4,
        help="Learning rate (default: 2e-4)",
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=16,
        help="LoRA rank (default: 16)",
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=2048,
        help="Maximum sequence length (default: 2048)",
    )
    parser.add_argument(
        "--save-merged",
        action="store_true",
        help="Save merged model after training",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fast iteration settings (10 steps, small batches)",
    )

    args = parser.parse_args()

    if args.fast:
        from tunacode.training.config import fast_iteration_config

        config = fast_iteration_config()
        config.dataset_path = args.dataset
        config.output_dir = args.output
        config.model_name = args.model
    else:
        from tunacode.training.config import LoraConfig

        config = TrainingConfig(
            model_name=args.model,
            dataset_path=args.dataset,
            output_dir=args.output,
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            max_seq_length=args.max_seq_length,
            lora=LoraConfig(r=args.lora_r),
        )

    adapter_path = train(config)
    logger.info("LoRA adapter saved to: %s", adapter_path)

    if args.save_merged:
        merged_path = save_merged_model(config)
        logger.info("Merged model saved to: %s", merged_path)


if __name__ == "__main__":
    main()
