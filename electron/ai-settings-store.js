const fs = require('fs');
const path = require('path');

const DEFAULT_SYSTEM_PROMPT = `You are a Python programming assistant integrated into BlockMirror, a visual Python editor.
Your primary task is to generate Python code based on user requirements.

Rules:
1. Always wrap generated Python code in \`\`\`python code blocks
2. Provide clear, well-commented code
3. Use standard Python libraries when possible
4. Keep code concise and readable
5. If the user's request is unclear, ask for clarification
6. When modifying existing code, show the complete updated version`;

class AiSettingsStore {
    constructor(userDataPath) {
        this.filePath = path.join(userDataPath, 'ai-settings.json');
        this.data = null;
        this.load();
    }

    load() {
        try {
            if (fs.existsSync(this.filePath)) {
                const raw = fs.readFileSync(this.filePath, 'utf-8');
                this.data = JSON.parse(raw);
                // Fix legacy "midium" typo
                if (this.data.effort === 'midium') {
                    this.data.effort = 'medium';
                    this.save();
                }
            } else {
                this.data = this._defaults();
            }
        } catch (err) {
            this.data = this._defaults();
        }
    }

    _defaults() {
        return {
            authToken: 'msk-480ffe4f47a434e3b657c3ba7b009c908223c484b79e8905fd1d89b282b29281',
            aigcUser: '',
            model: 'gpt-5',
            effort: 'medium',
            systemPrompt: DEFAULT_SYSTEM_PROMPT,
        };
    }

    save() {
        const dir = path.dirname(this.filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        const tmpPath = this.filePath + '.tmp';
        fs.writeFileSync(tmpPath, JSON.stringify(this.data, null, 2), 'utf-8');
        fs.renameSync(tmpPath, this.filePath);
    }

    getAll() {
        return { ...this.data };
    }

    update(newData) {
        if (newData.authToken !== undefined) this.data.authToken = newData.authToken;
        if (newData.aigcUser !== undefined) this.data.aigcUser = newData.aigcUser;
        if (newData.model !== undefined) this.data.model = newData.model;
        if (newData.effort !== undefined) this.data.effort = newData.effort;
        if (newData.systemPrompt !== undefined) this.data.systemPrompt = newData.systemPrompt;
        this.save();
        return this.getAll();
    }
}

module.exports = { AiSettingsStore };
