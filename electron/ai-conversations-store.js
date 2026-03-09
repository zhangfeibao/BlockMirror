const fs = require('fs');
const path = require('path');

class AiConversationsStore {
    constructor(userDataPath) {
        this.filePath = path.join(userDataPath, 'ai-conversations.json');
        this.data = null;
        this.load();
    }

    load() {
        try {
            if (fs.existsSync(this.filePath)) {
                const raw = fs.readFileSync(this.filePath, 'utf-8');
                this.data = JSON.parse(raw);
                if (!Array.isArray(this.data.conversations)) {
                    this.data.conversations = [];
                }
            } else {
                this.data = { conversations: [] };
            }
        } catch (err) {
            this.data = { conversations: [] };
        }
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

    _generateId() {
        return 'conv_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 6);
    }

    getAll() {
        // Return list without full message content for performance
        return this.data.conversations.map(c => ({
            id: c.id,
            title: c.title,
            createdAt: c.createdAt,
            messageCount: c.messages.length,
        }));
    }

    get(id) {
        return this.data.conversations.find(c => c.id === id) || null;
    }

    create(title) {
        const conv = {
            id: this._generateId(),
            title: title || 'New Conversation',
            createdAt: Date.now(),
            messages: [],
        };
        this.data.conversations.unshift(conv);
        this.save();
        return conv;
    }

    addMessage(id, msg) {
        const conv = this.data.conversations.find(c => c.id === id);
        if (!conv) return null;
        conv.messages.push({
            role: msg.role,
            content: msg.content,
            timestamp: Date.now(),
        });
        this.save();
        return conv;
    }

    updateTitle(id, title) {
        const conv = this.data.conversations.find(c => c.id === id);
        if (!conv) return null;
        conv.title = title;
        this.save();
        return conv;
    }

    clearMessages(id) {
        const conv = this.data.conversations.find(c => c.id === id);
        if (!conv) return null;
        conv.messages = [];
        this.save();
        return conv;
    }

    delete(id) {
        const idx = this.data.conversations.findIndex(c => c.id === id);
        if (idx === -1) return false;
        this.data.conversations.splice(idx, 1);
        this.save();
        return true;
    }
}

module.exports = { AiConversationsStore };
