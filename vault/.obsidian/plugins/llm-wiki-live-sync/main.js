const { Plugin, PluginSettingTab, Setting, requestUrl, Notice } = require("obsidian");

const DEFAULT_SETTINGS = {
    apiUrl: "https://llm-wiki-kar.onrender.com",
    syncIntervalSeconds: 3,
    autoSync: true
};

function slugify(text) {
    if (!text) return "conversation";
    return text
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, "")
        .replace(/[\s_]+/g, "-")
        .substring(0, 50)
        .replace(/-+$/, "") || "conversation";
}

class LLMWikiLiveSyncPlugin extends Plugin {
    async onload() {
        await this.loadSettings();

        // 1. Add Status Bar Item
        this.statusBarItem = this.addStatusBarItem();
        this.updateStatusBar("🟢 Wiki Sync: Active");

        // 2. Add Ribbon Icon
        this.addRibbonIcon("refresh-cw", "Sync LLM Wiki Threads Now", async () => {
            new Notice("Syncing LLM Wiki threads...");
            await this.syncThreads();
            new Notice("LLM Wiki sync complete!");
        });

        // 3. Register Settings Tab
        this.addSettingTab(new LLMWikiSyncSettingTab(this.app, this));

        // 4. Start Background Live Sync
        this.startSyncTimer();

        // Initial sync on startup
        this.syncThreads();
    }

    onunload() {
        this.stopSyncTimer();
    }

    startSyncTimer() {
        this.stopSyncTimer();
        if (this.settings.autoSync) {
            const intervalMs = Math.max(2, this.settings.syncIntervalSeconds) * 1000;
            this.syncIntervalId = window.setInterval(() => {
                this.syncThreads();
            }, intervalMs);
        }
    }

    stopSyncTimer() {
        if (this.syncIntervalId) {
            window.clearInterval(this.syncIntervalId);
            this.syncIntervalId = null;
        }
    }

    updateStatusBar(text) {
        if (this.statusBarItem) {
            this.statusBarItem.setText(text);
        }
    }

    async syncThreads() {
        try {
            const baseUrl = this.settings.apiUrl.replace(/\/+$/, "");
            
            // 1. Fetch Remote Threads
            const threadsRes = await requestUrl({
                url: `${baseUrl}/api/threads`,
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            if (threadsRes.status !== 200 || !threadsRes.json) return;
            const threads = threadsRes.json.threads || [];

            // Ensure threads directory exists
            const adapter = this.app.vault.adapter;
            const threadsDir = "threads";
            if (!(await adapter.exists(threadsDir))) {
                await adapter.mkdir(threadsDir);
            }

            for (const th of threads) {
                const threadId = th.thread_id;
                const detailRes = await requestUrl({
                    url: `${baseUrl}/api/threads/${threadId}`,
                    method: "GET",
                    headers: { "Accept": "application/json" }
                });

                if (detailRes.status !== 200 || !detailRes.json) continue;
                const detail = detailRes.json;

                const user = detail.user || "shubh";
                const title = detail.title || "Skincare Inquiry";
                const slug = slugify(title);
                const createdDate = (detail.created_at || "").substring(0, 10) || new Date().toISOString().substring(0, 10);
                const fileName = `${user}_${slug}_${createdDate}.md`;
                const filePath = `${threadsDir}/${fileName}`;

                const turns = detail.turns || [];
                const turnsMd = turns.map(t => {
                    const timeStr = t.created_at ? t.created_at.substring(11, 19) : "";
                    return `## Turn ${t.turn_number || 1} — ${timeStr}\n\n**User:**\n${t.user_prompt || ""}\n\n**AI Response:**\n${t.ai_response || ""}\n`;
                }).join("\n---\n\n");

                const mdContent = `---
thread_id: "${threadId}"
user: "${user}"
title: "${title}"
created: "${detail.created_at || ""}"
last_updated: "${detail.last_updated || ""}"
turn_count: ${turns.length}
---

# ${user} — ${title} — ${createdDate}

---

${turnsMd}
`;
                // Compare before write to avoid unnecessary disk operations
                const exists = await adapter.exists(filePath);
                if (exists) {
                    const currentContent = await adapter.read(filePath);
                    if (currentContent !== mdContent) {
                        await adapter.write(filePath, mdContent);
                    }
                } else {
                    await adapter.write(filePath, mdContent);
                }
            }

            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            this.updateStatusBar(`🟢 Wiki Synced: ${timeStr}`);
        } catch (err) {
            // Quiet fail in background
            this.updateStatusBar("🟡 Wiki Sync: Connecting...");
        }
    }

    async loadSettings() {
        this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    }

    async saveSettings() {
        await this.saveData(this.settings);
        this.startSyncTimer();
    }
}

class LLMWikiSyncSettingTab extends PluginSettingTab {
    constructor(app, plugin) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display() {
        const { containerEl } = this;
        containerEl.empty();
        containerEl.createEl("h2", { text: "LLM Wiki Real-Time Sync Settings" });

        new Setting(containerEl)
            .setName("Backend API URL")
            .setDesc("The public URL of your Render backend.")
            .addText(text => text
                .setPlaceholder("https://llm-wiki-kar.onrender.com")
                .setValue(this.plugin.settings.apiUrl)
                .onChange(async (value) => {
                    this.plugin.settings.apiUrl = value.trim();
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName("Sync Interval (Seconds)")
            .setDesc("How frequently to check for new Claude/Cruz Brain turns (minimum 2s).")
            .addText(text => text
                .setPlaceholder("3")
                .setValue(String(this.plugin.settings.syncIntervalSeconds))
                .onChange(async (value) => {
                    const num = parseInt(value, 10);
                    if (!isNaN(num)) {
                        this.plugin.settings.syncIntervalSeconds = Math.max(2, num);
                        await this.plugin.saveSettings();
                    }
                }));

        new Setting(containerEl)
            .setName("Enable Background Auto-Sync")
            .setDesc("Automatically pull new threads live while Obsidian is open.")
            .addToggle(toggle => toggle
                .setValue(this.plugin.settings.autoSync)
                .onChange(async (value) => {
                    this.plugin.settings.autoSync = value;
                    await this.plugin.saveSettings();
                }));
    }
}

module.exports = LLMWikiLiveSyncPlugin;
