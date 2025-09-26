use std::fs::{self, File};
use std::io::BufReader;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use chrono::Utc;
use clap::Parser;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

const MEMORY_ROOT: &str = ".claude/memory_anchors";
const ANCHORS_FILE: &str = "anchors.json";

#[derive(Parser, Debug)]
#[command(version, about = "Drop a CLAUDE/AGENTS memory anchor for KB synch", long_about = None)]
struct Args {
    file: PathBuf,
    #[arg(value_parser = clap::value_parser!(usize))]
    line: usize,
    desc: String,
    kind: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct AnchorsRecord {
    version: u8,
    generated: String,
    anchors: Vec<AnchorEntry>,
}

impl AnchorsRecord {
    fn new() -> Self {
        Self {
            version: 1,
            generated: current_timestamp(),
            anchors: Vec::new(),
        }
    }

    fn touch_generated(&mut self) {
        self.generated = current_timestamp();
    }
}

#[derive(Serialize, Deserialize, Debug)]
struct AnchorEntry {
    key: String,
    path: String,
    line: usize,
    kind: String,
    description: String,
    status: String,
    created: String,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("Error: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let args = Args::parse();

    let file_path = args.file;
    let line_num = args.line;
    let description = args.desc;
    let kind = args.kind.unwrap_or_else(|| "line".to_string());

    if !file_path.exists() {
        println!("File {} not found.", file_path.display());
        return Ok(());
    }

    let mut lines = read_file_lines(&file_path)?;
    if line_num == 0 {
        println!(
            "Invalid line {} for file with {} lines.",
            line_num,
            lines.len()
        );
        return Ok(());
    }

    let max_valid = lines.len() + 1;
    if line_num > max_valid {
        println!(
            "Invalid line {} for file with {} lines.",
            line_num,
            lines.len()
        );
        return Ok(());
    }

    let key = generate_key();
    let comment = build_comment(&file_path, &key, &description);
    let insert_at = line_num - 1;
    lines.insert(insert_at, comment);
    fs::write(&file_path, lines.concat())
        .with_context(|| format!("Failed to write updated content to {}", file_path.display()))?;

    let anchor_root = PathBuf::from(MEMORY_ROOT);
    fs::create_dir_all(&anchor_root)
        .with_context(|| format!("Failed to create {}", anchor_root.display()))?;

    let anchors_path = anchor_root.join(ANCHORS_FILE);
    let mut record = load_record(&anchors_path)?;
    let now = current_timestamp();
    record.anchors.push(AnchorEntry {
        key: key.clone(),
        path: file_path.display().to_string(),
        line: line_num,
        kind,
        description,
        status: "active".to_string(),
        created: now,
    });
    record.touch_generated();
    write_record(&anchors_path, &record)?;

    println!(
        "Anchor {} dropped at {}:{}",
        key,
        file_path.display(),
        line_num
    );

    Ok(())
}

fn read_file_lines(path: &Path) -> Result<Vec<String>> {
    let content = fs::read_to_string(path)
        .with_context(|| format!("Failed to read file {}", path.display()))?;
    Ok(split_lines_preserve_newline(&content))
}

fn split_lines_preserve_newline(content: &str) -> Vec<String> {
    if content.is_empty() {
        Vec::new()
    } else {
        content
            .split_inclusive('\n')
            .map(|line| line.to_string())
            .collect()
    }
}

fn build_comment(path: &Path, key: &str, desc: &str) -> String {
    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| format!(".{}", s.to_lowercase()))
        .unwrap_or_default();
    let (prefix, suffix) = comment_tokens(&ext);
    format!("{prefix} CLAUDE_ANCHOR[key={key}] {desc}{suffix}\n")
}

fn comment_tokens(ext: &str) -> (&'static str, &'static str) {
    match ext {
        ".py" => ("#", ""),
        ".js" | ".ts" | ".go" | ".c" | ".cpp" | ".java" | ".rs" | ".zig" => ("//", ""),
        ".sql" => ("--", ""),
        ".html" | ".htm" => ("<!--", " -->"),
        _ => ("//", ""),
    }
}

fn generate_key() -> String {
    let uuid = Uuid::new_v4().to_string();
    uuid[..8].to_string()
}

fn load_record(path: &Path) -> Result<AnchorsRecord> {
    if !path.exists() {
        return Ok(AnchorsRecord::new());
    }

    let file = File::open(path)
        .with_context(|| format!("Failed to open anchors file {}", path.display()))?;
    let reader = BufReader::new(file);
    match serde_json::from_reader(reader) {
        Ok(record) => Ok(record),
        Err(_) => {
            println!("Invalid anchors.json; reinitializing.");
            Ok(AnchorsRecord::new())
        }
    }
}

fn write_record(path: &Path, record: &AnchorsRecord) -> Result<()> {
    let file = File::create(path)
        .with_context(|| format!("Failed to write anchors file {}", path.display()))?;
    serde_json::to_writer_pretty(file, record).context("Failed to serialize anchors record")
}

fn current_timestamp() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}