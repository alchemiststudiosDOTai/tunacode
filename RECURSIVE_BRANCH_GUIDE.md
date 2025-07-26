# Running the Recursive Task Execution Branch

## Quick Start

1. **Navigate to your TunaCode directory:**
   ```bash
   cd /path/to/your/tunacode
   ```

2. **Run the setup script:**
   ```bash
   ./run_recursive_branch.sh
   ```

   This script will:
   - Switch to the `feature/recursive-task-execution` branch
   - Pull latest changes
   - Set up/update the virtual environment
   - Install dependencies
   - Create a `tc-recursive` alias
   - Start TunaCode

## Manual Setup (Alternative)

If you prefer to set it up manually:

```bash
# 1. Navigate to your TunaCode directory
cd /path/to/your/tunacode

# 2. Switch to the recursive branch
git checkout feature/recursive-task-execution
git pull origin feature/recursive-task-execution

# 3. Set up virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 4. Install dependencies
pip install -e ".[dev]"

# 5. Run TunaCode
python -m tunacode
```

## Testing the Recursive Features

1. **Enable thoughts to see recursive execution in action:**
   ```
   /thoughts on
   ```

2. **Try a complex task that will trigger decomposition:**
   ```
   Build a complete REST API for a todo application with:
   - User authentication (JWT)
   - CRUD operations for todos
   - User-specific todo lists
   - Input validation
   - Error handling
   - Unit tests
   ```

3. **Watch the recursive decomposition:**
   - You'll see "🔄 RECURSIVE EXECUTION" messages
   - Task complexity analysis
   - Subtask breakdown
   - Progress tracking for each subtask

## Configuration

You can adjust recursive execution settings in your `~/.config/tunacode.json`:

```json
{
  "settings": {
    "use_recursive_execution": true,
    "recursive_complexity_threshold": 0.7,
    "max_recursion_depth": 5,
    "subtask_iteration_ratio": 0.3,
    "min_subtask_iterations": 10
  }
}
```

## Key Differences from Main Branch

1. **Automatic Task Decomposition**: Complex tasks are automatically broken down
2. **Iteration Budget Management**: Each subtask gets its own iteration budget
3. **Hierarchical Execution**: Tasks can spawn subtasks recursively
4. **Enhanced Progress UI**: Visual feedback for recursive execution
5. **Result Aggregation**: Subtask results are intelligently combined

## Troubleshooting

- **If recursive execution doesn't trigger:**
  - Check if `use_recursive_execution` is true in config
  - Ensure your task complexity is above threshold (0.7)
  - Enable `/thoughts on` to see analysis details

- **If you want to disable recursive execution:**
  ```
  /model
  ```
  Then set `use_recursive_execution` to false

## Switching Back to Main

To switch back to the main branch version:
```bash
git checkout master
pip install -e ".[dev]"
```

Then use your regular `tc` command.