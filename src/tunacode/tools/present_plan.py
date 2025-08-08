"""Tool for presenting a structured plan and exiting plan mode."""

from typing import List, Optional

from tunacode.tools.base import BaseTool
from tunacode.ui import console as ui
from tunacode.types import ToolResult, PlanDoc, PlanPhase


class PresentPlanTool(BaseTool):
    """Present a structured implementation plan and request user approval."""
    
    def __init__(self, state_manager, ui_logger=None):
        """Initialize the present plan tool.
        
        Args:
            state_manager: StateManager instance for controlling plan mode state
            ui_logger: UI logger instance for displaying messages
        """
        super().__init__(ui_logger)
        self.state_manager = state_manager
    
    @property
    def tool_name(self) -> str:
        return "present_plan"
    
    async def _execute(
        self,
        title: str,
        overview: str,
        steps: List[str],
        files_to_modify: List[str] = None,
        files_to_create: List[str] = None,
        risks: List[str] = None,
        tests: List[str] = None,
        rollback: Optional[str] = None,
        open_questions: List[str] = None,
        success_criteria: List[str] = None,
        references: List[str] = None,
    ) -> ToolResult:
        """Present the implementation plan for user approval."""
        
        # Create PlanDoc from parameters
        plan_doc = PlanDoc(
            title=title,
            overview=overview,
            steps=steps,
            files_to_modify=files_to_modify or [],
            files_to_create=files_to_create or [],
            risks=risks or [],
            tests=tests or [],
            rollback=rollback,
            open_questions=open_questions or [],
            success_criteria=success_criteria or [],
            references=references or []
        )
        
        # Validate the plan
        is_valid, missing_sections = plan_doc.validate()
        if not is_valid:
            return f"❌ Plan incomplete. Missing sections: {', '.join(missing_sections)}. Continue researching and refining your plan."
        
        # Set plan phase to PLAN_READY and store the plan
        # The REPL will handle displaying the plan when it detects PLAN_READY phase
        self.state_manager.session.plan_phase = PlanPhase.PLAN_READY
        self.state_manager.session.current_plan = plan_doc
        
        return "Plan ready for review. The system will now present it to the user for approval."
    
    async def _present_plan(self, plan_doc: PlanDoc) -> None:
        """Present the plan in a formatted way."""
        output = []
        output.append("")
        output.append("╭─────────────────────────────────────────────────────────╮")
        output.append("│                  📋 IMPLEMENTATION PLAN                │")
        output.append("╰─────────────────────────────────────────────────────────╯")
        output.append("")
        output.append(f"🎯 **{plan_doc.title}**")
        output.append("")
        
        if plan_doc.overview:
            output.append(f"📝 **Overview:** {plan_doc.overview}")
            output.append("")
        
        # Files section
        if plan_doc.files_to_modify:
            output.append("📝 **Files to Modify:**")
            for f in plan_doc.files_to_modify:
                output.append(f"  • {f}")
            output.append("")
            
        if plan_doc.files_to_create:
            output.append("📄 **Files to Create:**")
            for f in plan_doc.files_to_create:
                output.append(f"  • {f}")
            output.append("")
        
        # Implementation steps
        output.append("🔧 **Implementation Steps:**")
        for i, step in enumerate(plan_doc.steps, 1):
            output.append(f"  {i}. {step}")
        output.append("")
        
        # Testing approach
        if plan_doc.tests:
            output.append("🧪 **Testing Approach:**")
            for test in plan_doc.tests:
                output.append(f"  • {test}")
            output.append("")
        
        # Success criteria
        if plan_doc.success_criteria:
            output.append("✅ **Success Criteria:**")
            for criteria in plan_doc.success_criteria:
                output.append(f"  • {criteria}")
            output.append("")
        
        # Risks and considerations
        if plan_doc.risks:
            output.append("⚠️ **Risks & Considerations:**")
            for risk in plan_doc.risks:
                output.append(f"  • {risk}")
            output.append("")
        
        # Open questions
        if plan_doc.open_questions:
            output.append("❓ **Open Questions:**")
            for question in plan_doc.open_questions:
                output.append(f"  • {question}")
            output.append("")
        
        # References
        if plan_doc.references:
            output.append("📚 **References:**")
            for ref in plan_doc.references:
                output.append(f"  • {ref}")
            output.append("")
        
        # Rollback plan
        if plan_doc.rollback:
            output.append(f"🔄 **Rollback Plan:** {plan_doc.rollback}")
            output.append("")
        
        # Print everything at once
        await ui.info("\n".join(output))


def create_present_plan_tool(state_manager):
    """
    Factory function to create present_plan tool with the correct state manager.
    
    Args:
        state_manager: The StateManager instance to use
        
    Returns:
        Callable: The present_plan function bound to the provided state manager
    """
    async def present_plan(
        title: str,
        overview: str,
        steps: List[str],
        files_to_modify: List[str] = None,
        files_to_create: List[str] = None,
        risks: List[str] = None,
        tests: List[str] = None,
        rollback: Optional[str] = None,
        open_questions: List[str] = None,
        success_criteria: List[str] = None,
        references: List[str] = None,
    ) -> str:
        """
        Present a structured implementation plan for user approval.
        
        This tool should ONLY be called when you have a complete, well-researched plan.
        All required sections must be filled out before calling this tool.
        
        Args:
            title: Brief, descriptive title for the implementation plan
            overview: High-level summary of what needs to be implemented and why
            steps: Ordered list of specific implementation steps (required)
            files_to_modify: List of existing files that need to be modified
            files_to_create: List of new files that need to be created  
            risks: Potential risks, challenges, or considerations
            tests: Testing approach and test cases to validate implementation
            rollback: Plan for reverting changes if needed
            open_questions: Any remaining questions or uncertainties
            success_criteria: Specific criteria for considering the task complete
            references: External resources, documentation, or research sources
            
        Returns:
            str: Status message about plan presentation
        """
        tool = PresentPlanTool(state_manager=state_manager)
        return await tool._execute(
            title=title,
            overview=overview,
            steps=steps,
            files_to_modify=files_to_modify,
            files_to_create=files_to_create,
            risks=risks,
            tests=tests,
            rollback=rollback,
            open_questions=open_questions,
            success_criteria=success_criteria,
            references=references,
        )
    
    return present_plan