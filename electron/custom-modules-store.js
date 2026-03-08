const fs = require('fs');
const path = require('path');

class CustomModulesStore {
    constructor(userDataPath) {
        this.filePath = path.join(userDataPath, 'custom-modules.json');
        this.data = null;
        this.load();
    }

    load() {
        try {
            if (fs.existsSync(this.filePath)) {
                const raw = fs.readFileSync(this.filePath, 'utf-8');
                this.data = JSON.parse(raw);
                // 版本兼容检查
                if (!this.data.version) {
                    this.data.version = 1;
                }
                if (!Array.isArray(this.data.modules)) {
                    this.data.modules = [];
                }
            } else {
                this.data = { version: 1, modules: [] };
            }
        } catch (err) {
            // 数据损坏：创建备份后重置
            try {
                const backupPath = this.filePath + '.backup.' + Date.now();
                if (fs.existsSync(this.filePath)) {
                    fs.copyFileSync(this.filePath, backupPath);
                }
            } catch (_) { /* 备份失败也继续 */ }
            this.data = { version: 1, modules: [] };
        }
    }

    save() {
        const dir = path.dirname(this.filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        // 原子写入：先写临时文件再重命名
        const tmpPath = this.filePath + '.tmp';
        fs.writeFileSync(tmpPath, JSON.stringify(this.data, null, 2), 'utf-8');
        fs.renameSync(tmpPath, this.filePath);
    }

    getAll() {
        return this.data;
    }

    _generateId(prefix) {
        return prefix + '_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 6);
    }

    createModule({ name, colour, description }) {
        const mod = {
            id: this._generateId('mod'),
            name: name || '新模块',
            colour: colour !== undefined ? colour : 210,
            description: description || '',
            functions: [],
        };
        this.data.modules.push(mod);
        this.save();
        return mod;
    }

    updateModule(moduleId, data) {
        const mod = this.data.modules.find(m => m.id === moduleId);
        if (!mod) return null;
        if (data.name !== undefined) mod.name = data.name;
        if (data.colour !== undefined) mod.colour = data.colour;
        if (data.description !== undefined) mod.description = data.description;
        this.save();
        return mod;
    }

    deleteModule(moduleId) {
        const idx = this.data.modules.findIndex(m => m.id === moduleId);
        if (idx === -1) return false;
        this.data.modules.splice(idx, 1);
        this.save();
        return true;
    }

    createFunction(moduleId, fnData) {
        const mod = this.data.modules.find(m => m.id === moduleId);
        if (!mod) return null;
        const fn = {
            id: this._generateId('fn'),
            name: fnData.name || 'new_function',
            displayName: fnData.displayName || '',
            returns: fnData.returns || false,
            colour: fnData.colour !== undefined ? fnData.colour : mod.colour,
            params: fnData.params || [],
            fullParams: fnData.fullParams || [],
            module: fnData.module || '',
            toolboxSnippet: fnData.toolboxSnippet || '',
        };
        mod.functions.push(fn);
        this.save();
        return fn;
    }

    updateFunction(moduleId, fnId, fnData) {
        const mod = this.data.modules.find(m => m.id === moduleId);
        if (!mod) return null;
        const fn = mod.functions.find(f => f.id === fnId);
        if (!fn) return null;
        if (fnData.name !== undefined) fn.name = fnData.name;
        if (fnData.displayName !== undefined) fn.displayName = fnData.displayName;
        if (fnData.returns !== undefined) fn.returns = fnData.returns;
        if (fnData.colour !== undefined) fn.colour = fnData.colour;
        if (fnData.params !== undefined) fn.params = fnData.params;
        if (fnData.fullParams !== undefined) fn.fullParams = fnData.fullParams;
        if (fnData.module !== undefined) fn.module = fnData.module;
        if (fnData.toolboxSnippet !== undefined) fn.toolboxSnippet = fnData.toolboxSnippet;
        this.save();
        return fn;
    }

    deleteFunction(moduleId, fnId) {
        const mod = this.data.modules.find(m => m.id === moduleId);
        if (!mod) return false;
        const idx = mod.functions.findIndex(f => f.id === fnId);
        if (idx === -1) return false;
        mod.functions.splice(idx, 1);
        this.save();
        return true;
    }

    moveFunctionToModule(fnId, fromModuleId, toModuleId) {
        const fromMod = this.data.modules.find(m => m.id === fromModuleId);
        const toMod = this.data.modules.find(m => m.id === toModuleId);
        if (!fromMod || !toMod) return false;
        const idx = fromMod.functions.findIndex(f => f.id === fnId);
        if (idx === -1) return false;
        const fn = fromMod.functions.splice(idx, 1)[0];
        toMod.functions.push(fn);
        this.save();
        return true;
    }

    exportToFile(filePath, moduleId) {
        let exportData;
        if (moduleId) {
            const mod = this.data.modules.find(m => m.id === moduleId);
            if (!mod) return false;
            exportData = { version: 1, modules: [mod] };
        } else {
            exportData = this.data;
        }
        fs.writeFileSync(filePath, JSON.stringify(exportData, null, 2), 'utf-8');
        return true;
    }

    importFromFile(filePath) {
        const raw = fs.readFileSync(filePath, 'utf-8');
        const importData = JSON.parse(raw);
        if (!importData.modules || !Array.isArray(importData.modules)) {
            throw new Error('无效的模块数据文件');
        }
        // 为导入的模块和函数生成新 ID 避免冲突
        importData.modules.forEach(mod => {
            mod.id = this._generateId('mod');
            if (mod.functions) {
                mod.functions.forEach(fn => {
                    fn.id = this._generateId('fn');
                });
            } else {
                mod.functions = [];
            }
            this.data.modules.push(mod);
        });
        this.save();
        return importData.modules;
    }
}

module.exports = { CustomModulesStore };
