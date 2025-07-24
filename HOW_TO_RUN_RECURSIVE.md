# How to Run the Recursive Branch Version

## ✅ Fixed Issues

1. **Version Conflict Resolved** - You were running the old system version (0.0.36) instead of the recursive branch version (0.0.41)
2. **Path Issues Fixed** - Shell alias and wrapper script now ensure correct version
3. **Configuration Updated** - Recursive execution settings added to config

## 🚀 Three Ways to Run

### Option 1: Use the Wrapper Script (Recommended)
```bash
./tunacode-recursive
```
This automatically:
- Ensures you're on the correct branch
- Activates the virtual environment
- Uses the correct version (0.0.41)

### Option 2: Use the Shell Alias
```bash
# First, reload your shell or run:
source ~/.bashrc

# Then use:
tc-recursive
```

### Option 3: Manual Activation
```bash
cd /root/tunacode
source venv/bin/activate
tunacode
```

## 🧪 Verify It's Working

1. **Check Version**: You should see v0.0.41 features
2. **Enable Thoughts**: Type `/thoughts on` to see recursive execution details
3. **Test Complex Task**: Try this example:
   ```
   Build a complete REST API with authentication, CRUD operations, and tests
   ```

## 📋 What You'll See When It Works

When recursive execution triggers, you'll see:
```
🔄 RECURSIVE EXECUTION: Task complexity 0.85 >= 0.70
Reasoning: Task requires multiple distinct operations
Subtasks: 3
```

## ⚠️ Important Notes

- **Always use one of the methods above** - Don't just type `tunacode` without the venv
- **The warnings about "Main agent not available"** are expected in some contexts and don't affect functionality
- **Recursive features** only activate for complex tasks (complexity ≥ 0.7)

## 🔧 Configuration

Your config now includes:
- `use_recursive_execution`: true
- `recursive_complexity_threshold`: 0.7 
- `max_recursion_depth`: 5
- `subtask_iteration_ratio`: 0.3
- `min_subtask_iterations`: 10

Change these in `~/.config/tunacode.json` if needed.