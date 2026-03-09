"""
Variable List Panel - Hierarchical tree view of symbols
"""

import os
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTreeView, QGroupBox,
    QAbstractItemView, QHeaderView
)
from PySide6.QtCore import Signal, Slot, Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem

from ..symbol_resolver import SymbolResolver


class VariableListPanel(QWidget):
    """Panel displaying hierarchical list of variables"""

    variable_double_clicked = Signal(dict)  # Emits variable info

    def __init__(self, parent=None):
        super().__init__(parent)

        self._resolver: Optional[SymbolResolver] = None
        self._model = QStandardItemModel()
        self._proxy_model = QSortFilterProxyModel()

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        group = QGroupBox("Variables")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)

        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search variables...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        group_layout.addWidget(self.search_edit)

        # Tree view
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)

        # Set up model
        self._model.setHorizontalHeaderLabels(["Name"])
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setRecursiveFilteringEnabled(True)
        self.tree_view.setModel(self._proxy_model)

        group_layout.addWidget(self.tree_view)

    def set_resolver(self, resolver: SymbolResolver):
        """Set the symbol resolver and populate the tree"""
        self._resolver = resolver
        self._populate_tree()

    def _populate_tree(self):
        """Populate tree view with symbols"""
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["Name"])

        if not self._resolver:
            return

        # Group symbols by source file
        file_groups: Dict[str, List[dict]] = {}
        for symbol in self._resolver.symbols:
            source_file = symbol.get('sourceFile', 'Unknown')
            # Use basename for display
            display_file = os.path.basename(source_file) if source_file else 'Unknown'

            if display_file not in file_groups:
                file_groups[display_file] = []
            file_groups[display_file].append(symbol)

        # Create tree structure
        root = self._model.invisibleRootItem()

        for file_name in sorted(file_groups.keys()):
            file_item = QStandardItem(file_name)
            file_item.setData('file', Qt.UserRole)
            file_item.setData({'type': 'file', 'name': file_name}, Qt.UserRole + 1)

            for symbol in sorted(file_groups[file_name], key=lambda x: x.get('name', '')):
                self._add_symbol_item(file_item, symbol)

            root.appendRow(file_item)

    def _add_symbol_item(self, parent: QStandardItem, symbol: dict):
        """Add a symbol and its members to the tree"""
        name = symbol.get('name', 'Unknown')
        data_type = symbol.get('dataType', '')
        address = symbol.get('memoryAddress', '')
        size = symbol.get('sizeInBytes', 0)
        is_struct = symbol.get('isStruct', False)
        is_array = symbol.get('isArray', False)

        # Create display text
        display = name
        if is_array:
            dims = symbol.get('arrayDimensions', [])
            if dims:
                display = f"{name}[{dims[0]}]"

        item = QStandardItem(display)
        item.setData('variable', Qt.UserRole)

        # Store full symbol info
        var_info = {
            'type': 'variable',
            'name': name,
            'path': name,
            'dataType': data_type,
            'baseType': symbol.get('baseDataType', data_type),
            'address': address,
            'size': size,
            'isStruct': is_struct,
            'isArray': is_array,
            'arrayDimensions': symbol.get('arrayDimensions', []),
            'sourceFile': symbol.get('sourceFile', '')
        }
        item.setData(var_info, Qt.UserRole + 1)

        # Set tooltip
        tooltip = f"Name: {name}\nType: {data_type}\nAddress: {address}\nSize: {size} bytes"
        item.setToolTip(tooltip)

        # Add struct members
        if is_struct:
            members = symbol.get('members', [])
            for member in members:
                self._add_member_item(item, member, name)

        parent.appendRow(item)

    def _add_member_item(self, parent: QStandardItem, member: dict, parent_path: str):
        """Add a struct member to the tree"""
        name = member.get('name', 'Unknown')
        data_type = member.get('dataType', '')
        offset = member.get('offset', 0)
        size = member.get('sizeInBytes', 0)
        is_struct = member.get('isStruct', False)
        is_array = member.get('isArray', False)

        # Create display text
        display = name
        if is_array:
            dims = member.get('arrayDimensions', [])
            if dims:
                display = f"{name}[{dims[0]}]"

        item = QStandardItem(display)
        item.setData('member', Qt.UserRole)

        # Full path
        full_path = f"{parent_path}.{name}"

        var_info = {
            'type': 'member',
            'name': name,
            'path': full_path,
            'dataType': data_type,
            'baseType': member.get('baseDataType', data_type),
            'offset': offset,
            'size': size,
            'isStruct': is_struct,
            'isArray': is_array,
            'arrayDimensions': member.get('arrayDimensions', [])
        }
        item.setData(var_info, Qt.UserRole + 1)

        # Set tooltip
        tooltip = f"Name: {full_path}\nType: {data_type}\nOffset: {offset}\nSize: {size} bytes"
        item.setToolTip(tooltip)

        # Recursively add nested struct members
        if is_struct:
            nested_members = member.get('members', [])
            for nested in nested_members:
                self._add_member_item(item, nested, full_path)

        parent.appendRow(item)

    @Slot(str)
    def _on_search_changed(self, text: str):
        """Handle search text change"""
        self._proxy_model.setFilterFixedString(text)

        # Expand all if searching
        if text:
            self.tree_view.expandAll()

    @Slot()
    def _on_item_double_clicked(self, index):
        """Handle double-click on tree item"""
        source_index = self._proxy_model.mapToSource(index)
        item = self._model.itemFromIndex(source_index)

        if not item:
            return

        item_type = item.data(Qt.UserRole)

        # Only allow double-click on variables and members (not file nodes)
        if item_type in ('variable', 'member'):
            var_info = item.data(Qt.UserRole + 1)
            if var_info:
                self.variable_double_clicked.emit(var_info)
