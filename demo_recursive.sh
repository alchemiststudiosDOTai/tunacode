#!/bin/bash

echo "🚀 TunaCode Recursive Execution Demo"
echo "===================================="
echo ""
echo "This demo will show the recursive task execution in action."
echo ""
echo "Features to observe:"
echo "  • Automatic task decomposition for complex tasks"
echo "  • Iteration budget management"
echo "  • Hierarchical task execution"
echo "  • Progress tracking"
echo ""
echo "Press Enter to start TunaCode..."
read

# Create a demo input file with commands
cat > /tmp/tunacode_demo_input.txt << 'EOF'
/thoughts on
Build a complete REST API for a todo application with user authentication, CRUD operations, input validation, database integration, and comprehensive tests
/exit
EOF

echo ""
echo "📝 Demo commands prepared:"
echo "  1. Enable thoughts to see recursive execution"
echo "  2. Submit a complex task"
echo "  3. Exit"
echo ""
echo "Starting TunaCode with demo input..."
echo ""

# Run TunaCode with the demo input
source venv/bin/activate
tunacode < /tmp/tunacode_demo_input.txt

echo ""
echo "🎉 Demo complete!"
echo ""
echo "To run TunaCode interactively:"
echo "  $ tunacode"
echo ""
echo "Or use the alias (after restarting terminal):"
echo "  $ tc-recursive"