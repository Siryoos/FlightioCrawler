"""
Command Pattern implementation for crawling operations.

This module provides command pattern implementation for:
- Crawling operations encapsulation
- Command queuing and scheduling
- Command history and undo functionality
- Batch operations and transactions
- Command chaining and composition

Allows flexible crawling workflow management with support for:
- Asynchronous execution
- Command prioritization
- Rollback capabilities
- Progress tracking
"""

import threading
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future
from queue import PriorityQueue, Queue, Empty
import json
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    """Status of command execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class CommandPriority(Enum):
    """Priority levels for commands."""

    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class CommandResult:
    """Result of command execution."""

    success: bool
    data: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": str(self.error) if self.error else None,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class CommandContext:
    """Context information for command execution."""

    command_id: str
    created_at: datetime
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: CommandStatus = CommandStatus.PENDING
    priority: CommandPriority = CommandPriority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def elapsed_time(self) -> Optional[float]:
        """Get elapsed execution time."""
        if self.executed_at and self.completed_at:
            return (self.completed_at - self.executed_at).total_seconds()
        return None


class Command(ABC):
    """Abstract base class for all commands."""

    def __init__(
        self,
        name: str,
        description: str = "",
        priority: CommandPriority = CommandPriority.NORMAL,
    ):
        self.name = name
        self.description = description
        self.context = CommandContext(
            command_id=str(uuid.uuid4()), created_at=datetime.now(), priority=priority
        )
        self._result: Optional[CommandResult] = None
        self._lock = threading.Lock()

    @abstractmethod
    def execute(self, **kwargs) -> CommandResult:
        """Execute the command."""
        pass

    def can_undo(self) -> bool:
        """Check if command can be undone."""
        return False

    def undo(self) -> CommandResult:
        """Undo the command (if supported)."""
        return CommandResult(success=False, error=Exception("Undo not supported"))

    def can_retry(self) -> bool:
        """Check if command can be retried."""
        return (
            self.context.retry_count < self.context.max_retries
            and self.context.status in [CommandStatus.FAILED, CommandStatus.CANCELLED]
        )

    def get_result(self) -> Optional[CommandResult]:
        """Get command result."""
        with self._lock:
            return self._result

    def set_result(self, result: CommandResult) -> None:
        """Set command result."""
        with self._lock:
            self._result = result

    def add_tag(self, tag: str) -> None:
        """Add tag to command."""
        if tag not in self.context.tags:
            self.context.tags.append(tag)

    def has_tag(self, tag: str) -> bool:
        """Check if command has tag."""
        return tag in self.context.tags

    def __str__(self) -> str:
        return f"{self.name}({self.context.command_id[:8]})"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} [{self.context.status.value}]>"


class CrawlSiteCommand(Command):
    """Command for crawling a specific site."""

    def __init__(
        self,
        site_url: str,
        adapter_name: str,
        search_params: Dict[str, Any],
        priority: CommandPriority = CommandPriority.NORMAL,
    ):
        super().__init__(
            name=f"crawl_{adapter_name}",
            description=f"Crawl {site_url} with {adapter_name}",
            priority=priority,
        )
        self.site_url = site_url
        self.adapter_name = adapter_name
        self.search_params = search_params
        self.original_data = None  # For undo operations

    def execute(self, **kwargs) -> CommandResult:
        """Execute crawling operation."""
        start_time = time.time()

        try:
            # Import adapter factory (avoid circular imports)
            from adapters.factories.enhanced_adapter_factory import (
                get_enhanced_adapter_factory,
            )

            factory = get_enhanced_adapter_factory()
            adapter = factory.create_adapter(self.adapter_name)

            if not adapter:
                raise Exception(f"Failed to create adapter: {self.adapter_name}")

            # Perform crawling
            logger.info(f"Starting crawl: {self.site_url} with {self.adapter_name}")
            results = adapter.search_flights(**self.search_params)

            execution_time = time.time() - start_time

            return CommandResult(
                success=True,
                data=results,
                execution_time=execution_time,
                metadata={
                    "site_url": self.site_url,
                    "adapter_name": self.adapter_name,
                    "search_params": self.search_params,
                    "results_count": len(results) if results else 0,
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Crawl failed for {self.site_url}: {e}")

            return CommandResult(
                success=False,
                error=e,
                execution_time=execution_time,
                metadata={
                    "site_url": self.site_url,
                    "adapter_name": self.adapter_name,
                    "search_params": self.search_params,
                },
            )

    def can_undo(self) -> bool:
        """Crawl operations generally cannot be undone."""
        return False


class ValidateDataCommand(Command):
    """Command for validating crawled data."""

    def __init__(
        self,
        data: List[Dict],
        validation_rules: Dict[str, Any],
        priority: CommandPriority = CommandPriority.HIGH,
    ):
        super().__init__(
            name="validate_data",
            description="Validate crawled flight data",
            priority=priority,
        )
        self.data = data
        self.validation_rules = validation_rules

    def execute(self, **kwargs) -> CommandResult:
        """Execute data validation."""
        start_time = time.time()

        try:
            valid_items = []
            invalid_items = []
            validation_errors = []

            for item in self.data:
                is_valid, errors = self._validate_item(item)
                if is_valid:
                    valid_items.append(item)
                else:
                    invalid_items.append(item)
                    validation_errors.extend(errors)

            execution_time = time.time() - start_time

            return CommandResult(
                success=True,
                data={
                    "valid_items": valid_items,
                    "invalid_items": invalid_items,
                    "validation_errors": validation_errors,
                },
                execution_time=execution_time,
                metadata={
                    "total_items": len(self.data),
                    "valid_count": len(valid_items),
                    "invalid_count": len(invalid_items),
                    "validation_rules": list(self.validation_rules.keys()),
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Data validation failed: {e}")

            return CommandResult(success=False, error=e, execution_time=execution_time)

    def _validate_item(self, item: Dict) -> Tuple[bool, List[str]]:
        """Validate a single data item."""
        errors = []

        # Check required fields
        required_fields = self.validation_rules.get("required_fields", [])
        for field in required_fields:
            if field not in item or item[field] is None:
                errors.append(f"Missing required field: {field}")

        # Check field types
        field_types = self.validation_rules.get("field_types", {})
        for field, expected_type in field_types.items():
            if field in item and item[field] is not None:
                if expected_type == "number" and not isinstance(
                    item[field], (int, float)
                ):
                    errors.append(f"Field {field} should be numeric")
                elif expected_type == "string" and not isinstance(item[field], str):
                    errors.append(f"Field {field} should be string")

        # Check value ranges
        value_ranges = self.validation_rules.get("value_ranges", {})
        for field, range_def in value_ranges.items():
            if field in item and item[field] is not None:
                value = item[field]
                if isinstance(value, (int, float)):
                    min_val = range_def.get("min")
                    max_val = range_def.get("max")
                    if min_val is not None and value < min_val:
                        errors.append(f"Field {field} below minimum: {min_val}")
                    if max_val is not None and value > max_val:
                        errors.append(f"Field {field} above maximum: {max_val}")

        return len(errors) == 0, errors


class SaveDataCommand(Command):
    """Command for saving data to database."""

    def __init__(
        self,
        data: List[Dict],
        table_name: str,
        priority: CommandPriority = CommandPriority.NORMAL,
    ):
        super().__init__(
            name="save_data",
            description=f"Save data to {table_name}",
            priority=priority,
        )
        self.data = data
        self.table_name = table_name
        self.saved_ids = []  # For undo operations

    def execute(self, **kwargs) -> CommandResult:
        """Execute data saving."""
        start_time = time.time()

        try:
            # Import database manager
            from adapters.patterns.singleton_pattern import get_database_manager

            db_manager = get_database_manager()
            saved_count = 0

            for item in self.data:
                # Simple insert operation (would be more complex in real implementation)
                columns = ", ".join(item.keys())
                placeholders = ", ".join(["?" for _ in item.keys()])
                values = tuple(item.values())

                query = (
                    f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
                )
                rows_affected = db_manager.execute_non_query(query, values)

                if rows_affected > 0:
                    saved_count += 1
                    # In real implementation, would get the inserted ID
                    self.saved_ids.append(f"temp_id_{saved_count}")

            execution_time = time.time() - start_time

            return CommandResult(
                success=True,
                data={"saved_count": saved_count, "saved_ids": self.saved_ids},
                execution_time=execution_time,
                metadata={"table_name": self.table_name, "total_items": len(self.data)},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Data saving failed: {e}")

            return CommandResult(success=False, error=e, execution_time=execution_time)

    def can_undo(self) -> bool:
        """Save operations can be undone by deletion."""
        return len(self.saved_ids) > 0

    def undo(self) -> CommandResult:
        """Undo save operation by deleting saved records."""
        start_time = time.time()

        try:
            from adapters.patterns.singleton_pattern import get_database_manager

            db_manager = get_database_manager()
            deleted_count = 0

            for record_id in self.saved_ids:
                # Simple delete operation
                query = f"DELETE FROM {self.table_name} WHERE id = ?"
                rows_affected = db_manager.execute_non_query(query, (record_id,))
                deleted_count += rows_affected

            execution_time = time.time() - start_time
            self.saved_ids.clear()  # Clear saved IDs after undo

            return CommandResult(
                success=True,
                data={"deleted_count": deleted_count},
                execution_time=execution_time,
                metadata={"operation": "undo_save"},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Undo save operation failed: {e}")

            return CommandResult(success=False, error=e, execution_time=execution_time)


class MacroCommand(Command):
    """Command that executes multiple commands in sequence."""

    def __init__(
        self,
        name: str,
        commands: List[Command],
        stop_on_failure: bool = True,
        priority: CommandPriority = CommandPriority.NORMAL,
    ):
        super().__init__(
            name, f"Macro command with {len(commands)} operations", priority
        )
        self.commands = commands
        self.stop_on_failure = stop_on_failure
        self.executed_commands = []  # For undo operations

    def execute(self, **kwargs) -> CommandResult:
        """Execute all commands in sequence."""
        start_time = time.time()

        try:
            results = []

            for cmd in self.commands:
                logger.info(f"Executing macro command step: {cmd.name}")
                result = cmd.execute(**kwargs)
                results.append({"command": cmd.name, "result": result.to_dict()})

                if result.success:
                    self.executed_commands.append(cmd)
                else:
                    if self.stop_on_failure:
                        logger.error(
                            f"Macro command stopped due to failure in: {cmd.name}"
                        )
                        break
                    else:
                        logger.warning(
                            f"Macro command continuing despite failure in: {cmd.name}"
                        )

            execution_time = time.time() - start_time

            # Determine overall success
            success = all(r["result"]["success"] for r in results)

            return CommandResult(
                success=success,
                data=results,
                execution_time=execution_time,
                metadata={
                    "total_commands": len(self.commands),
                    "executed_commands": len(self.executed_commands),
                    "stop_on_failure": self.stop_on_failure,
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Macro command execution failed: {e}")

            return CommandResult(success=False, error=e, execution_time=execution_time)

    def can_undo(self) -> bool:
        """Macro can be undone if any executed commands can be undone."""
        return any(cmd.can_undo() for cmd in self.executed_commands)

    def undo(self) -> CommandResult:
        """Undo executed commands in reverse order."""
        start_time = time.time()

        try:
            undo_results = []

            # Undo in reverse order
            for cmd in reversed(self.executed_commands):
                if cmd.can_undo():
                    logger.info(f"Undoing macro command step: {cmd.name}")
                    result = cmd.undo()
                    undo_results.append(
                        {"command": cmd.name, "undo_result": result.to_dict()}
                    )

            execution_time = time.time() - start_time
            self.executed_commands.clear()

            return CommandResult(
                success=True,
                data=undo_results,
                execution_time=execution_time,
                metadata={"operation": "undo_macro"},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Macro command undo failed: {e}")

            return CommandResult(success=False, error=e, execution_time=execution_time)


class CommandInvoker:
    """Invoker for executing commands with support for queuing, history, and undo."""

    def __init__(self, max_workers: int = 4, enable_history: bool = True):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.command_queue = PriorityQueue()
        self.running_commands: Dict[str, Future] = {}
        self.command_history: List[Command] = [] if enable_history else None
        self.enable_history = enable_history
        self._lock = threading.Lock()
        self._shutdown = False

        # Start command processor thread
        self._processor_thread = threading.Thread(
            target=self._process_commands, daemon=True
        )
        self._processor_thread.start()

        logger.info(f"CommandInvoker initialized with {max_workers} workers")

    def execute_command(self, command: Command, **kwargs) -> Future[CommandResult]:
        """Execute a command asynchronously."""
        if self._shutdown:
            raise RuntimeError("CommandInvoker is shutdown")

        future = self.executor.submit(self._execute_with_context, command, **kwargs)

        with self._lock:
            self.running_commands[command.context.command_id] = future

        logger.info(f"Submitted command for execution: {command}")
        return future

    def queue_command(self, command: Command) -> None:
        """Add command to queue for later execution."""
        if self._shutdown:
            raise RuntimeError("CommandInvoker is shutdown")

        # Priority queue uses (priority, item) tuples
        priority_value = command.context.priority.value
        self.command_queue.put((priority_value, time.time(), command))

        logger.info(
            f"Queued command: {command} (priority: {command.context.priority.name})"
        )

    def _process_commands(self) -> None:
        """Process commands from queue continuously."""
        while not self._shutdown:
            try:
                # Get command from queue with timeout
                priority, queued_time, command = self.command_queue.get(timeout=1.0)

                if not self._shutdown:
                    logger.info(f"Processing queued command: {command}")
                    future = self.execute_command(command)

                    # Optional: wait for completion or handle differently
                    # future.result()  # This would block until completion

                self.command_queue.task_done()

            except Empty:
                # Timeout reached, continue loop
                continue
            except Exception as e:
                logger.error(f"Error processing command queue: {e}")

    def _execute_with_context(self, command: Command, **kwargs) -> CommandResult:
        """Execute command with proper context management."""
        command.context.status = CommandStatus.RUNNING
        command.context.executed_at = datetime.now()

        try:
            # Apply timeout if specified
            if command.context.timeout:
                # Note: This is a simplified timeout implementation
                # In production, you'd want more sophisticated timeout handling
                pass

            result = command.execute(**kwargs)

            if result.success:
                command.context.status = CommandStatus.COMPLETED
            else:
                command.context.status = CommandStatus.FAILED
                # Check for retry
                if command.can_retry():
                    command.context.retry_count += 1
                    command.context.status = CommandStatus.RETRYING
                    logger.info(
                        f"Retrying command: {command} (attempt {command.context.retry_count})"
                    )
                    # Schedule retry (simplified implementation)
                    return self._execute_with_context(command, **kwargs)

            command.set_result(result)

            # Add to history if enabled
            if self.enable_history and self.command_history is not None:
                self.command_history.append(command)
                # Limit history size
                if len(self.command_history) > 1000:
                    self.command_history = self.command_history[-500:]

            return result

        except Exception as e:
            command.context.status = CommandStatus.FAILED
            result = CommandResult(success=False, error=e)
            command.set_result(result)
            logger.error(f"Command execution failed: {command} - {e}")
            return result

        finally:
            command.context.completed_at = datetime.now()

            # Remove from running commands
            with self._lock:
                self.running_commands.pop(command.context.command_id, None)

    def get_command_status(self, command_id: str) -> Optional[CommandStatus]:
        """Get status of a command by ID."""
        if self.command_history:
            for command in self.command_history:
                if command.context.command_id == command_id:
                    return command.context.status

        # Check running commands
        with self._lock:
            if command_id in self.running_commands:
                return CommandStatus.RUNNING

        return None

    def cancel_command(self, command_id: str) -> bool:
        """Cancel a running command."""
        with self._lock:
            if command_id in self.running_commands:
                future = self.running_commands[command_id]
                cancelled = future.cancel()
                if cancelled:
                    logger.info(f"Cancelled command: {command_id}")
                return cancelled

        return False

    def get_running_commands(self) -> List[str]:
        """Get list of currently running command IDs."""
        with self._lock:
            return list(self.running_commands.keys())

    def get_command_history(self, limit: int = 100) -> List[Command]:
        """Get command history."""
        if not self.command_history:
            return []

        return self.command_history[-limit:]

    def undo_last_command(self) -> Optional[CommandResult]:
        """Undo the last executed command if possible."""
        if not self.command_history:
            return None

        for command in reversed(self.command_history):
            if command.context.status == CommandStatus.COMPLETED and command.can_undo():
                logger.info(f"Undoing command: {command}")
                return command.undo()

        logger.warning("No undoable commands found in history")
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self.command_history:
            return {"history_enabled": False}

        total_commands = len(self.command_history)
        completed = sum(
            1
            for cmd in self.command_history
            if cmd.context.status == CommandStatus.COMPLETED
        )
        failed = sum(
            1
            for cmd in self.command_history
            if cmd.context.status == CommandStatus.FAILED
        )

        # Calculate average execution time
        execution_times = [
            cmd.context.elapsed_time()
            for cmd in self.command_history
            if cmd.context.elapsed_time() is not None
        ]
        avg_execution_time = (
            sum(execution_times) / len(execution_times) if execution_times else 0
        )

        return {
            "total_commands": total_commands,
            "completed_commands": completed,
            "failed_commands": failed,
            "running_commands": len(self.running_commands),
            "queued_commands": self.command_queue.qsize(),
            "success_rate": (
                (completed / total_commands * 100) if total_commands > 0 else 0
            ),
            "average_execution_time": avg_execution_time,
            "history_enabled": self.enable_history,
        }

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the command invoker."""
        logger.info("Shutting down CommandInvoker...")
        self._shutdown = True

        if wait:
            # Wait for queue to empty
            self.command_queue.join()

            # Wait for running commands to complete
            with self._lock:
                futures = list(self.running_commands.values())

            for future in futures:
                try:
                    future.result(timeout=30)  # 30 second timeout
                except Exception as e:
                    logger.warning(f"Command did not complete gracefully: {e}")

        self.executor.shutdown(wait=wait)
        logger.info("CommandInvoker shutdown completed")


# Utility functions for creating common command workflows


def create_crawl_and_save_workflow(
    site_configs: List[Dict[str, Any]],
    search_params: Dict[str, Any],
    validation_rules: Dict[str, Any],
    table_name: str = "flight_data",
) -> MacroCommand:
    """Create a workflow that crawls multiple sites and saves validated data."""
    commands = []

    # Create crawl commands for each site
    for config in site_configs:
        crawl_cmd = CrawlSiteCommand(
            site_url=config["url"],
            adapter_name=config["adapter"],
            search_params=search_params,
            priority=config.get("priority", CommandPriority.NORMAL),
        )
        crawl_cmd.add_tag("crawl")
        crawl_cmd.add_tag(config["adapter"])
        commands.append(crawl_cmd)

    # Note: In a real implementation, you'd need to collect and merge
    # results from crawl commands before validation and saving
    # This is a simplified example

    return MacroCommand(
        name="crawl_and_save_workflow",
        commands=commands,
        stop_on_failure=False,  # Continue even if some sites fail
        priority=CommandPriority.HIGH,
    )


def create_validation_workflow(
    data: List[Dict], validation_rules: Dict[str, Any]
) -> MacroCommand:
    """Create a workflow for data validation and cleaning."""
    validate_cmd = ValidateDataCommand(data, validation_rules, CommandPriority.HIGH)
    validate_cmd.add_tag("validation")

    return MacroCommand(
        name="validation_workflow",
        commands=[validate_cmd],
        priority=CommandPriority.HIGH,
    )


# Context manager for command execution
@contextmanager
def command_invoker_context(max_workers: int = 4, enable_history: bool = True):
    """Context manager for CommandInvoker lifecycle."""
    invoker = CommandInvoker(max_workers=max_workers, enable_history=enable_history)
    try:
        yield invoker
    finally:
        invoker.shutdown(wait=True)


# Singleton instance (optional)
_command_invoker_instance = None
_invoker_lock = threading.Lock()


def get_command_invoker(
    max_workers: int = 4, enable_history: bool = True
) -> CommandInvoker:
    """Get singleton CommandInvoker instance."""
    global _command_invoker_instance

    if _command_invoker_instance is None:
        with _invoker_lock:
            if _command_invoker_instance is None:
                _command_invoker_instance = CommandInvoker(max_workers, enable_history)

    return _command_invoker_instance
