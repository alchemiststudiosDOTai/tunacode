"""Tool for exiting plan mode and presenting implementation plan."""

from typing import Any, Dict, List

from tunacode.tools.base import BaseTool
from tunacode.ui import console as ui
from tunacode.types import ToolResult


class ExitPlanModeTool(BaseTool):
    """Present implementation plan and exit plan mode."""
    
    def __init__(self, state_manager, ui_logger=None):
        """Initialize the exit plan mode tool.
        
        Args:
            state_manager: StateManager instance for controlling plan mode state
            ui_logger: UI logger instance for displaying messages
        """
        super().__init__(ui_logger)
        self.state_manager = state_manager
    
    @property
    def tool_name(self) -> str:
        return "exit_plan_mode"
    
    async def _execute(
        self,
        plan_title: str,
        overview: str,
        implementation_steps: List[str],
        files_to_modify: List[str] = None,
        files_to_create: List[str] = None,
        risks_and_considerations: List[str] = None,
        testing_approach: str = None,
        success_criteria: List[str] = None,
    ) -> ToolResult:
        """Present the implementation plan and get user approval."""
        
        plan = {
            "title": plan_title,
            "overview": overview,
            "files_to_modify": files_to_modify or [],
            "files_to_create": files_to_create or [],
            "implementation_steps": implementation_steps,
            "risks_and_considerations": risks_and_considerations or [],
            "testing_approach": testing_approach or "Manual testing of functionality",
            "success_criteria": success_criteria or []
        }
        
        # Present plan to user
        await self._present_plan(plan)
        
        # Get user approval
        approved = await self._get_user_approval()
        
        # Update state based on user approval
        if approved:
            # Store the plan and exit plan mode
            self.state_manager.set_current_plan(plan)
            self.state_manager.exit_plan_mode(plan)
            await ui.success("✅ Plan approved! Exiting Plan Mode.")
            return "Plan approved and Plan Mode exited. You can now execute the implementation using write tools (write_file, update_file, bash, run_command)."
        else:
            # Keep the plan but stay in plan mode
            self.state_manager.set_current_plan(plan)
            await ui.warning("❌ Plan rejected. Staying in Plan Mode for further research.")
            return "Plan rejected. Continue researching and refine your approach. You remain in Plan Mode - only read-only tools are available."
    
    async def _present_plan(self, plan: Dict[str, Any]) -> None:
        """Present the plan in a formatted way."""
        # Build the entire plan output as a single string to avoid UI flooding
        output = []
        output.append("")
        output.append("╭─────────────────────────────────────────────────────────╮")
        output.append("│                  📋 IMPLEMENTATION PLAN                │")
        output.append("╰─────────────────────────────────────────────────────────╯")
        output.append("")
        output.append(f"🎯 {plan['title']}")
        output.append("")
        
        if plan["overview"]:
            output.append(f"📝 Overview: {plan['overview']}")
            output.append("")
        
        # Files section
        if plan["files_to_modify"]:
            output.append("📝 Files to Modify:")
            for f in plan["files_to_modify"]:
                output.append(f"  • {f}")
            output.append("")
            
        if plan["files_to_create"]:
            output.append("📄 Files to Create:")
            for f in plan["files_to_create"]:
                output.append(f"  • {f}")
            output.append("")
        
        # Implementation steps
        output.append("🔧 Implementation Steps:")
        for i, step in enumerate(plan["implementation_steps"], 1):
            output.append(f"  {i}. {step}")
        output.append("")
        
        # Testing approach
        if plan["testing_approach"]:
            output.append(f"🧪 Testing Approach: {plan['testing_approach']}")
            output.append("")
        
        # Success criteria
        if plan["success_criteria"]:
            output.append("✅ Success Criteria:")
            for criteria in plan["success_criteria"]:
                output.append(f"  • {criteria}")
            output.append("")
        
        # Risks and considerations
        if plan["risks_and_considerations"]:
            output.append("⚠️ Risks & Considerations:")
            for risk in plan["risks_and_considerations"]:
                output.append(f"  • {risk}")
            output.append("")
        
        # Print everything at once
        await ui.info("\n".join(output))
    
    async def _get_user_approval(self) -> bool:
        """Get user approval for the plan."""
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.patch_stdout import patch_stdout
            
            session = PromptSession()
            
            with patch_stdout():
                response = await session.prompt_async("\n🤔 Approve this implementation plan? (y/n): ")
            
            return response.strip().lower() in ['y', 'yes', 'approve']
        except (KeyboardInterrupt, EOFError):
            return False


def create_exit_plan_mode_tool(state_manager):
    """
    Factory function to create exit_plan_mode tool with the correct state manager.
    
    Args:
        state_manager: The StateManager instance to use
        
    Returns:
        Callable: The exit_plan_mode function bound to the provided state manager
    """
    async def exit_plan_mode(
        plan_title: str,
        overview: str,
        implementation_steps: List[str],
        files_to_modify: List[str] = None,
        files_to_create: List[str] = None,
        risks_and_considerations: List[str] = None,
        testing_approach: str = None,
        success_criteria: List[str] = None,
    ) -> str:
        """
        Present implementation plan and exit plan mode.
        
        Args:
            plan_title: Brief title for the implementation plan
            overview: High-level overview of the changes needed
            implementation_steps: Ordered list of implementation steps  
            files_to_modify: List of files that need to be modified
            files_to_create: List of new files to be created
            risks_and_considerations: Potential risks or important considerations
            testing_approach: Approach for testing the implementation
            success_criteria: Criteria for considering the implementation successful
            
        Returns:
            str: Result message indicating plan approval status
        """
        tool = ExitPlanModeTool(state_manager=state_manager)
        return await tool._execute(
            plan_title=plan_title,
            overview=overview,
            implementation_steps=implementation_steps,
            files_to_modify=files_to_modify,
            files_to_create=files_to_create,
            risks_and_considerations=risks_and_considerations,
            testing_approach=testing_approach,
            success_criteria=success_criteria,
        )
    
    return exit_plan_mode