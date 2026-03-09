"""
Variable Parser - Parse variable specifications like struct.member[index]@file

Supports:
- Simple variables: val
- Structure members: struct.member
- Array elements: array[0]
- Array ranges: array[0..4] (expands to array[0], array[1], ..., array[4])
- Combined access: struct.arr[2].field
- File filter: var@filename
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


@dataclass
class Accessor:
    """Represents a single accessor (.member or [index])"""
    type: str  # 'member', 'index', or 'range'
    value: str  # member name or index as string
    end_value: Optional[str] = None  # end index for range type

    def __str__(self):
        if self.type == 'member':
            return f".{self.value}"
        elif self.type == 'range':
            return f"[{self.value}..{self.end_value}]"
        else:
            return f"[{self.value}]"


@dataclass
class VariablePath:
    """Parsed variable path"""
    base_name: str
    file_filter: Optional[str] = None
    accessors: List[Accessor] = field(default_factory=list)

    def __str__(self):
        result = self.base_name
        for acc in self.accessors:
            result += str(acc)
        if self.file_filter:
            result += f"@{self.file_filter}"
        return result


@dataclass
class Assignment:
    """Parsed assignment expression (var=value)"""
    variable: VariablePath
    value: str


class VariableParser:
    """Parse variable specifications and assignments"""

    # Pattern for variable specification
    # Matches: base_name(.member)*([index] or [start..end])*(@file)?
    VAR_PATTERN = re.compile(r'''
        ^
        (?P<base>\w+)               # Base variable name
        (?P<access>(?:              # Access chain
            \.\w+                   # .member
            |
            \[\d+(?:\.\.\d+)?\]     # [index] or [start..end]
        )*)
        (?:@(?P<file>[\w.]+))?      # Optional @filename (with extension)
        $
    ''', re.VERBOSE)

    # Pattern for member access
    MEMBER_PATTERN = re.compile(r'\.(\w+)')

    # Pattern for index access (single index)
    INDEX_PATTERN = re.compile(r'\[(\d+)\]')

    # Pattern for range access [start..end]
    RANGE_PATTERN = re.compile(r'\[(\d+)\.\.(\d+)\]')

    @classmethod
    def parse_variable(cls, spec: str) -> VariablePath:
        """
        Parse variable specification

        Args:
            spec: Variable specification string
                  Examples: "val", "struct.member", "array[0]", "val@main"

        Returns:
            VariablePath object

        Raises:
            ValueError: If specification is invalid
        """
        spec = spec.strip()

        match = cls.VAR_PATTERN.match(spec)
        if not match:
            raise ValueError(f"Invalid variable specification: {spec}")

        base = match.group('base')
        file_filter = match.group('file')
        access_str = match.group('access') or ''

        # Parse accessors
        accessors = []
        pos = 0
        while pos < len(access_str):
            if access_str[pos] == '.':
                # Member access
                member_match = cls.MEMBER_PATTERN.match(access_str, pos)
                if member_match:
                    accessors.append(Accessor('member', member_match.group(1)))
                    pos = member_match.end()
                else:
                    raise ValueError(f"Invalid member access at position {pos}")
            elif access_str[pos] == '[':
                # Try range access first [start..end]
                range_match = cls.RANGE_PATTERN.match(access_str, pos)
                if range_match:
                    start_idx = range_match.group(1)
                    end_idx = range_match.group(2)
                    if int(start_idx) > int(end_idx):
                        raise ValueError(
                            f"Invalid range: start index must be <= end index"
                        )
                    accessors.append(Accessor('range', start_idx, end_idx))
                    pos = range_match.end()
                else:
                    # Try single index access [index]
                    index_match = cls.INDEX_PATTERN.match(access_str, pos)
                    if index_match:
                        accessors.append(Accessor('index', index_match.group(1)))
                        pos = index_match.end()
                    else:
                        raise ValueError(f"Invalid index access at position {pos}")
            else:
                raise ValueError(f"Unexpected character at position {pos}")

        return VariablePath(base, file_filter, accessors)

    @classmethod
    def parse_assignment(cls, expr: str) -> Assignment:
        """
        Parse assignment expression

        Args:
            expr: Assignment expression (e.g., "val=123", "struct.member = 456")

        Returns:
            Assignment object

        Raises:
            ValueError: If expression is invalid
        """
        expr = expr.strip()

        if '=' not in expr:
            raise ValueError(f"Invalid assignment (no '='): {expr}")

        # Split on first '=' to allow values containing '='
        var_part, value_part = expr.split('=', 1)
        var_part = var_part.strip()
        value_part = value_part.strip()

        if not var_part:
            raise ValueError("Empty variable name in assignment")
        if not value_part:
            raise ValueError("Empty value in assignment")

        variable = cls.parse_variable(var_part)
        return Assignment(variable, value_part)

    @classmethod
    def parse_variable_list(cls, spec: str) -> List[VariablePath]:
        """
        Parse comma-separated variable list

        Args:
            spec: Comma-separated variable specifications
                  Example: "val1,val2,struct.member"

        Returns:
            List of VariablePath objects
        """
        variables = []
        for part in spec.split(','):
            part = part.strip()
            if part:
                variables.append(cls.parse_variable(part))
        return variables

    @classmethod
    def parse_assignment_list(cls, spec: str) -> List[Assignment]:
        """
        Parse comma-separated assignment list

        Args:
            spec: Comma-separated assignments
                  Example: "val1=1,val2=12,val3=4"

        Returns:
            List of Assignment objects
        """
        assignments = []
        for part in spec.split(','):
            part = part.strip()
            if part:
                assignments.append(cls.parse_assignment(part))
        return assignments


def _expand_ranges(var_path: VariablePath) -> List[VariablePath]:
    """
    Expand range accessors in a VariablePath to individual paths.

    For example, arr[0..2] expands to [arr[0], arr[1], arr[2]]

    Args:
        var_path: VariablePath that may contain range accessors

    Returns:
        List of VariablePath objects with ranges expanded to individual indices
    """
    # Check if there are any range accessors
    has_range = any(acc.type == 'range' for acc in var_path.accessors)
    if not has_range:
        return [var_path]

    # Find the first range accessor and expand it
    result = []
    for i, acc in enumerate(var_path.accessors):
        if acc.type == 'range':
            start_idx = int(acc.value)
            end_idx = int(acc.end_value)

            # Create a new path for each index in the range
            for idx in range(start_idx, end_idx + 1):
                new_accessors = (
                    var_path.accessors[:i] +
                    [Accessor('index', str(idx))] +
                    var_path.accessors[i + 1:]
                )
                new_path = VariablePath(
                    base_name=var_path.base_name,
                    file_filter=var_path.file_filter,
                    accessors=new_accessors
                )
                # Recursively expand any remaining ranges
                result.extend(_expand_ranges(new_path))
            break

    return result


def parse_variables(spec: str) -> List[VariablePath]:
    """
    Convenience function to parse variable list with range expansion.

    Supports range syntax like arr[0..4] which expands to arr[0], arr[1], ..., arr[4].

    Args:
        spec: Comma-separated variable specifications

    Returns:
        List of VariablePath objects (ranges expanded)
    """
    raw_paths = VariableParser.parse_variable_list(spec)
    # Expand any range accessors
    result = []
    for path in raw_paths:
        result.extend(_expand_ranges(path))
    return result


def parse_assignments(spec: str) -> List[Assignment]:
    """
    Convenience function to parse assignment list

    Args:
        spec: Comma-separated assignments

    Returns:
        List of Assignment objects
    """
    return VariableParser.parse_assignment_list(spec)
