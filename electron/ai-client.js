const https = require('https');

const API_BASE = 'https://aimpapi.midea.com';
const GPT5_PATH = '/t-aigc/mip-chat-app/openai/standard/v1/chat/completions';
const CLAUDE_PATH = '/t-aigc/mip-chat-app/claude/official/standard/sync/v2/chat/completions';

const GPT5_BIZ_ID = 'gpt-5';
const CLAUDE_BIZ_ID = 'anthropic.claude-sonnet-4-5-20250929-v1:0';

const REQUEST_TIMEOUT = 5 * 60 * 1000; // 5 minutes

class AiClient {
    /**
     * Send a message to the LLM API.
     * @param {Array} messages - Array of {role, content} message objects
     * @param {Object} config - {model, authToken, aigcUser, effort, systemPrompt}
     * @returns {Promise<{content: string, error: string|null}>}
     */
    async sendMessage(messages, config) {
        const { model, authToken, aigcUser, effort, systemPrompt } = config;

        if (!authToken || !aigcUser) {
            return { content: null, error: 'Please configure AuthToken and AIGC-USER in AI settings first.' };
        }

        try {
            if (model === 'claude') {
                return await this._sendClaude(messages, { authToken, aigcUser, systemPrompt });
            } else {
                return await this._sendGpt5(messages, { authToken, aigcUser, effort, systemPrompt });
            }
        } catch (err) {
            return { content: null, error: err.message || String(err) };
        }
    }

    async _sendGpt5(messages, { authToken, aigcUser, effort, systemPrompt }) {
        // Build input array in GPT-5 format
        const input = [];

        if (systemPrompt) {
            input.push({ role: 'developer', content: systemPrompt });
        }

        for (const msg of messages) {
            input.push({ role: msg.role, content: msg.content });
        }

        const body = {
            model: 'gpt-5',
            reasoning: {
                effort: effort || 'medium',
                summary: 'auto',
            },
            stream: false,
            input: input,
        };

        const responseText = await this._request(GPT5_PATH, GPT5_BIZ_ID, authToken, aigcUser, body);
        const data = JSON.parse(responseText);

        // Format 1: OpenAI style { choices: [{ message: { content } }] }
        if (data.choices && data.choices[0] && data.choices[0].message) {
            return { content: data.choices[0].message.content, error: null };
        }

        // Format 2: GPT5 style { output: [{ type: 'message', content: [{ text }] }] }
        if (data.output && Array.isArray(data.output)) {
            const texts = [];
            for (const item of data.output) {
                if (item.type === 'message' && Array.isArray(item.content)) {
                    for (const block of item.content) {
                        if (block.text) texts.push(block.text);
                    }
                }
            }
            if (texts.length > 0) {
                return { content: texts.join('\n'), error: null };
            }
        }

        return { content: null, error: 'Unexpected response format: ' + responseText.substring(0, 500) };
    }

    async _sendClaude(messages, { authToken, aigcUser, systemPrompt }) {
        // Build Claude request format
        const claudeMessages = messages.map(msg => ({
            role: msg.role,
            content: [{ text: msg.content }],
        }));

        const body = {
            modelId: CLAUDE_BIZ_ID,
            messages: claudeMessages,
            additionalModelRequestFields: {
                thinking: {
                    type: 'enabled',
                    budget_tokens: 8000,
                },
            },
            inferenceConfig: {
                maxTokens: 32000,
            },
        };

        if (systemPrompt) {
            body.system = [{ text: systemPrompt }];
        }

        const responseText = await this._request(CLAUDE_PATH, CLAUDE_BIZ_ID, authToken, aigcUser, body);
        const data = JSON.parse(responseText);

        // Claude format: { output: { message: { content: [{ text }] } } }
        if (data.output && data.output.message && Array.isArray(data.output.message.content)) {
            const texts = [];
            for (const block of data.output.message.content) {
                if (block.text) texts.push(block.text);
            }
            if (texts.length > 0) {
                return { content: texts.join('\n'), error: null };
            }
        }

        return { content: null, error: 'Unexpected Claude response format: ' + responseText.substring(0, 500) };
    }

    _request(apiPath, bizId, authToken, aigcUser, body) {
        return new Promise((resolve, reject) => {
            const parsed = new URL(API_BASE);
            const postData = JSON.stringify(body);

            const options = {
                hostname: parsed.hostname,
                port: 443,
                path: apiPath,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Aimp-Biz-Id': bizId,
                    'Authorization': authToken,
                    'AIGC-USER': aigcUser,
                    'Content-Length': Buffer.byteLength(postData),
                },
                timeout: REQUEST_TIMEOUT,
            };

            const req = https.request(options, (res) => {
                const chunks = [];
                res.on('data', (chunk) => chunks.push(chunk));
                res.on('end', () => {
                    const responseBody = Buffer.concat(chunks).toString('utf-8');
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        resolve(responseBody);
                    } else {
                        reject(new Error(`API error (HTTP ${res.statusCode}): ${responseBody.substring(0, 500)}`));
                    }
                });
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timed out (5 minutes)'));
            });

            req.on('error', (err) => {
                reject(new Error('Network error: ' + err.message));
            });

            req.write(postData);
            req.end();
        });
    }
}

module.exports = { AiClient };
