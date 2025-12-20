"""Training configuration for Unsloth fine-tuning with QLoRA.

This module defines the TrainingConfig dataclass with all hyperparameters
needed for training LLMs on tool-calling patterns using Unsloth/QLoRA.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LoraConfig:
    """QLoRA adapter configuration.

    Attributes:
        r: LoRA rank (dimension of low-rank matrices)
        lora_alpha: LoRA scaling factor
        lora_dropout: Dropout probability for LoRA layers
        target_modules: Module names to apply LoRA to
        bias: Bias training strategy ("none", "all", "lora_only")
        use_gradient_checkpointing: Enable gradient checkpointing to save VRAM
        use_rslora: Use Rank-Stabilized LoRA for better convergence
    """

    r: int = 16
    lora_alpha: int = 16
    lora_dropout: float = 0.0
    target_modules: list[str] = field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )
    bias: str = "none"
    use_gradient_checkpointing: bool = True
    use_rslora: bool = False


@dataclass
class TrainingConfig:
    """Complete training configuration for Unsloth fine-tuning.

    Attributes:
        model_name: HuggingFace model identifier or local path
        dataset_path: Path to JSONL training data file
        output_dir: Directory for saving checkpoints and final model
        max_seq_length: Maximum sequence length for tokenization
        load_in_4bit: Use 4-bit quantization (QLoRA)
        lora: LoRA adapter configuration
        per_device_train_batch_size: Batch size per GPU
        gradient_accumulation_steps: Steps to accumulate before optimizer step
        warmup_steps: Number of warmup steps for learning rate scheduler
        max_steps: Maximum training steps (-1 for full dataset)
        num_train_epochs: Number of training epochs
        learning_rate: Initial learning rate
        weight_decay: Weight decay for AdamW optimizer
        logging_steps: Steps between logging
        save_steps: Steps between checkpoint saves
        eval_steps: Steps between evaluation runs
        seed: Random seed for reproducibility
        fp16: Use FP16 mixed precision
        bf16: Use BF16 mixed precision (preferred for newer GPUs)
        optim: Optimizer name (use "adamw_8bit" for memory efficiency)
        lr_scheduler_type: Learning rate scheduler type
        report_to: Reporting destinations (e.g., ["tensorboard", "wandb"])
        push_to_hub: Whether to push model to HuggingFace Hub
        hub_model_id: Model ID for HuggingFace Hub upload
    """

    model_name: str = "unsloth/qwen3-4b"
    dataset_path: Path = field(default_factory=lambda: Path("data/training.jsonl"))
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    max_seq_length: int = 2048
    load_in_4bit: bool = True

    lora: LoraConfig = field(default_factory=LoraConfig)

    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 5
    max_steps: int = -1
    num_train_epochs: int = 1
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    logging_steps: int = 1
    save_steps: int = 50
    eval_steps: int = 50
    seed: int = 42
    fp16: bool = False
    bf16: bool = True
    optim: str = "adamw_8bit"
    lr_scheduler_type: str = "linear"
    report_to: list[str] = field(default_factory=lambda: ["tensorboard"])
    push_to_hub: bool = False
    hub_model_id: str | None = None

    def to_sft_trainer_args(self) -> dict:
        """Convert to arguments for SFTTrainer from trl.

        Returns:
            Dictionary of arguments compatible with SFTTrainer/TrainingArguments.
        """
        return {
            "output_dir": str(self.output_dir),
            "per_device_train_batch_size": self.per_device_train_batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_steps": self.warmup_steps,
            "max_steps": self.max_steps,
            "num_train_epochs": self.num_train_epochs,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "logging_steps": self.logging_steps,
            "save_steps": self.save_steps,
            "eval_steps": self.eval_steps,
            "seed": self.seed,
            "fp16": self.fp16,
            "bf16": self.bf16,
            "optim": self.optim,
            "lr_scheduler_type": self.lr_scheduler_type,
            "report_to": self.report_to,
            "push_to_hub": self.push_to_hub,
            "hub_model_id": self.hub_model_id,
        }

    def to_lora_args(self) -> dict:
        """Convert LoRA config to arguments for get_peft_model.

        Returns:
            Dictionary of LoRA arguments for Unsloth's FastLanguageModel.
        """
        return {
            "r": self.lora.r,
            "lora_alpha": self.lora.lora_alpha,
            "lora_dropout": self.lora.lora_dropout,
            "target_modules": self.lora.target_modules,
            "bias": self.lora.bias,
            "use_gradient_checkpointing": self.lora.use_gradient_checkpointing,
            "use_rslora": self.lora.use_rslora,
        }


def default_config() -> TrainingConfig:
    """Create a default training configuration optimized for tool-calling.

    Returns:
        TrainingConfig with sensible defaults for fine-tuning on tool-calling data.
    """
    return TrainingConfig()


def small_gpu_config() -> TrainingConfig:
    """Create a configuration optimized for GPUs with limited VRAM (8-12GB).

    Uses smaller batch sizes, more aggressive gradient accumulation,
    and additional memory optimizations.

    Returns:
        TrainingConfig optimized for small GPUs.
    """
    return TrainingConfig(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        max_seq_length=1024,
        lora=LoraConfig(
            r=8,
            use_gradient_checkpointing=True,
        ),
    )


def fast_iteration_config() -> TrainingConfig:
    """Create a configuration for fast iteration and testing.

    Uses minimal settings for quick feedback during development.

    Returns:
        TrainingConfig for fast iteration.
    """
    return TrainingConfig(
        max_steps=10,
        logging_steps=1,
        save_steps=5,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        max_seq_length=512,
        lora=LoraConfig(r=4),
    )


def full_gpu_config() -> TrainingConfig:
    """Create optimal configuration for good GPUs (16GB+ VRAM).

    Uses recommended hyperparameters from Unsloth docs and community:
    - Higher LoRA rank (32) for better capacity
    - lora_alpha = 2x rank for stable training
    - Larger batch size with gradient accumulation
    - Cosine LR scheduler with warmup

    Returns:
        TrainingConfig optimized for full GPU training.
    """
    return TrainingConfig(
        model_name="unsloth/qwen3-4b",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        num_train_epochs=3,
        learning_rate=2e-4,
        warmup_steps=10,
        max_seq_length=2048,
        lr_scheduler_type="cosine",
        logging_steps=5,
        save_steps=100,
        lora=LoraConfig(
            r=32,
            lora_alpha=64,
            lora_dropout=0.0,
            use_gradient_checkpointing=True,
            use_rslora=False,
        ),
    )
