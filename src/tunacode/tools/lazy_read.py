"""
Lazy file reading tool for efficient content access.

This tool integrates with the context provider to read files only when needed,
supporting batch operations and caching for improved performance.
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Union

from tunacode.core.agents.context_provider import ContextProvider
from tunacode.exceptions import ToolExecutionError
from tunacode.tools.base import FileBasedTool


class LazyReadTool(FileBasedTool):
    """Tool for lazy file reading with caching and batch support."""
    
    def __init__(self, context_provider: ContextProvider = None, ui_logger=None):
        super().__init__(ui_logger)
        if context_provider is None:
            # Create default context provider for current directory
            self.context_provider = ContextProvider(Path.cwd())
        else:
            self.context_provider = context_provider
    
    @property
    def tool_name(self) -> str:
        return "lazy_read"
    
    async def _execute(
        self,
        file_paths: Union[str, List[str]],
        batch: bool = False
    ) -> str:
        """
        Read file(s) lazily with caching support.
        
        Args:
            file_paths: Single file path or list of file paths
            batch: Whether to read multiple files in batch mode
            
        Returns:
            File content(s) as formatted string
        """
        try:
            # Convert to list if single path
            if isinstance(file_paths, str):
                paths = [Path(file_paths)]
                batch = False
            else:
                paths = [Path(p) for p in file_paths]
                batch = True
            
            if batch:
                # Batch read multiple files
                file_contents = await self.context_provider.batch_read_files(paths)
                
                # Format output
                output_parts = []
                for path, content in file_contents.items():
                    if content is not None:
                        output_parts.append(f"=== {path} ===")
                        output_parts.append(content)
                        output_parts.append("")
                    else:
                        output_parts.append(f"=== {path} ===")
                        output_parts.append("[Could not read file]")
                        output_parts.append("")
                
                return "\n".join(output_parts)
            else:
                # Single file read
                path = paths[0]
                content = await self.context_provider.read_file_lazy(path)
                
                if content is not None:
                    return content
                else:
                    raise ToolExecutionError(f"Could not read file: {path}")
                    
        except Exception as e:
            raise ToolExecutionError(f"Lazy read failed: {str(e)}")


async def lazy_read_file(
    file_path: str,
    context_provider: Optional[ContextProvider] = None
) -> str:
    """
    Read a file lazily with caching.
    
    Args:
        file_path: Path to the file to read
        context_provider: Optional context provider instance
        
    Returns:
        File content as string
    """
    tool = LazyReadTool(context_provider)
    return await tool._execute(file_path, batch=False)


async def lazy_read_files(
    file_paths: List[str],
    context_provider: Optional[ContextProvider] = None
) -> str:
    """
    Read multiple files in batch with caching.
    
    Args:
        file_paths: List of file paths to read
        context_provider: Optional context provider instance
        
    Returns:
        Formatted string with all file contents
    """
    tool = LazyReadTool(context_provider)
    return await tool._execute(file_paths, batch=True)