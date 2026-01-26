// Orbyte v3.1 - Holo-Graphic Interface JavaScript

const MONACO_BASE = "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min";

// --- Monaco AMD bootstrap ---
window.monacoReady = new Promise((resolve, reject) => {
    try {
        window.require = window.require || {};
        window.require.config({
            paths: { vs: MONACO_BASE + "/vs" }
        });

        window.MonacoEnvironment = {
            getWorkerUrl: function (moduleId, label) {
                const code = `
          self.MonacoEnvironment = { baseUrl: '${MONACO_BASE}' };
          importScripts('${MONACO_BASE}/vs/base/worker/workerMain.js');
        `;
                return URL.createObjectURL(new Blob([code], { type: "text/javascript" }));
            }
        };

        window.require(["vs/editor/editor.main"], function () {
            resolve(window.monaco);
        });
    } catch (e) {
        console.error('Monaco loading failed:', e);
        resolve(null); // Continue without Monaco
    }
});

class OrbyteInterface {
    // --- SCRIPTS/TABS STATE ---
    scripts = []; // [{name, content, saved, path}]
    openTabs = []; // [{name, content, saved, path, monacoModel, _changeDisposable}]
    activeTabIndex = -1;
    monaco = null;
    monacoEditor = null;
    editorReady = false;
    defaultEditorOptions = null;

    constructor() {
        // Cache all DOM elements for performance
        this.DOM = {
            scriptsSidebar: document.getElementById('scriptsSidebar'),
            scriptsList: document.getElementById('scriptsList'),
            editorTabs: document.getElementById('editorTabs'),
            newScriptBtn: document.getElementById('newScriptBtn'),
            editorErrorBar: document.getElementById('editorErrorBar'),
            scriptsListViewport: document.getElementById('scriptsListViewport'),

            loadingScreen: document.getElementById('loadingScreen'),
            app: document.getElementById('app'),
            tokenModal: document.getElementById('tokenModal'),
            tokenInput: document.getElementById('tokenInput'),
            tokenError: document.getElementById('tokenError'),
            submitTokenBtn: document.getElementById('submitTokenBtn'),
            avatarImg: document.getElementById('avatarImg'),
            userName: document.getElementById('userName'),
            userId: document.getElementById('userId'),
            userInfoBadges: document.getElementById('userInfoBadges'),
            userInfoNitro: document.getElementById('userInfoNitro'),
            userIdInfo: document.getElementById('userIdInfo'),
            loadingStatus: document.getElementById('loadingStatus'),

            // Controller Modal
            controllerModal: document.getElementById('controllerModal'),
            controllerTokenInput: document.getElementById('controllerTokenInput'),
            controllerError: document.getElementById('controllerError'),
            saveControllerBtn: document.getElementById('saveControllerBtn'),
            skipControllerBtn: document.getElementById('skipControllerBtn'),
            guideControllerBtn: document.getElementById('guideControllerBtn'),
            backToSetupBtn: document.getElementById('backToSetupBtn'),
            controllerSetupView: document.getElementById('controllerSetupView'),
            controllerGuideView: document.getElementById('controllerGuideView'),

            // Dashboard Stats
            serverCount: document.getElementById('serverCount'),
            friendCount: document.getElementById('friendCount'),
            uptime: document.getElementById('uptime'),
            serversDate: document.getElementById('servers-date'),
            friendsDate: document.getElementById('friends-date'),
            uptimeDate: document.getElementById('uptime-date'),

            activityLog: document.getElementById('activityLog'),
            navItems: document.querySelectorAll('.nav-item'),
            pages: document.querySelectorAll('.page'),
            codeEditorWrapper: document.getElementById('codeEditorWrapper'),
            codeEditorContainer: document.getElementById('codeEditorContainer'),
            timeRangeSelector: document.getElementById('timeRangeSelector'),
            messagesChart: document.getElementById('messagesChart'),
            reactionsChart: document.getElementById('reactionsChart'),
            pingsChart: document.getElementById('pingsChart'),
            serversChart: document.getElementById('serversChart'),

            // Script Runner
            runScriptBtn: document.getElementById('runScriptBtn'),
            stopScriptBtn: document.getElementById('stopScriptBtn'),
            clearConsoleBtn: document.getElementById('clearConsoleBtn'),
            consoleOutput: document.getElementById('consoleOutput')
        };

        this.charts = {};
        this.lastCleanup = 0; // To avoid too frequent cleanups
        this.init();
    }

    init() {
        // --- SCRIPTS SIDEBAR & TABS ---
        if (this.DOM.newScriptBtn) {
            this.DOM.newScriptBtn.onclick = () => this.createNewScript();
        }
        // Keyboard shortcut: Ctrl+S to save
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                this.saveActiveScript();
            }
        });
        // Initial load of scripts list
        this.loadScriptsList();
        console.log("🚀 Orbyte Interface Initializing...");

        // Defer component initialization until the DOM is fully loaded.

        this.DOM.submitTokenBtn.addEventListener('click', () => this.handleTokenSubmit());
        this.DOM.tokenInput.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') this.handleTokenSubmit();
        });

        // Controller Modal Events
        if (this.DOM.saveControllerBtn) {
            this.DOM.saveControllerBtn.addEventListener('click', () => this.handleControllerSubmit());
        }
        if (this.DOM.skipControllerBtn) {
            this.DOM.skipControllerBtn.addEventListener('click', () => this.handleControllerSkip());
        }
        if (this.DOM.guideControllerBtn) {
            this.DOM.guideControllerBtn.addEventListener('click', () => this.showControllerGuide());
        }
        if (this.DOM.backToSetupBtn) {
            this.DOM.backToSetupBtn.addEventListener('click', () => this.backToControllerSetup());
        }

        // Script Runner
        if (this.DOM.runScriptBtn) this.DOM.runScriptBtn.onclick = () => this.runCurrentScript();
        if (this.DOM.stopScriptBtn) this.DOM.stopScriptBtn.onclick = () => this.stopCurrentScript();
        if (this.DOM.clearConsoleBtn) this.DOM.clearConsoleBtn.onclick = () => this.clearConsole();

        // Keyboard shortcut for Run (Ctrl+Enter)
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                if (document.getElementById('editor').classList.contains('active')) {
                    this.runCurrentScript();
                }
            }
        });

        this.DOM.navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleNavClick(e.currentTarget.dataset.page);
            });
        });
    }

    initTooltipDelegation() {
        const container = this.DOM.userInfoBadges;
        const tooltip = document.getElementById("global-tooltip");
        let hideTimeout;

        const show = (icon) => {
            if (!icon) return;
            const text = icon.dataset.tip || icon.getAttribute('aria-label');
            if (!text) return;

            // Replace line breaks and multiple spaces with a single space
            const normalizedText = text.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();

            tooltip.textContent = normalizedText;
            tooltip.style.display = 'block';
            tooltip.style.opacity = '1';

            requestAnimationFrame(() => {
                const rect = icon.getBoundingClientRect();
                const ttRect = tooltip.getBoundingClientRect();

                let left = rect.left + rect.width / 2 - ttRect.width / 2;
                left = Math.max(8, Math.min(left, window.innerWidth - ttRect.width - 8));

                let top = rect.top - ttRect.height - 8;
                if (top < 8) top = rect.bottom + 8;

                tooltip.style.left = `${left}px`;
                tooltip.style.top = `${top}px`;
            });
        };

        const hide = () => {
            tooltip.style.opacity = '0';
            if (hideTimeout) clearTimeout(hideTimeout);
            hideTimeout = setTimeout(() => {
                tooltip.style.display = 'none';
                hideTimeout = null;
            }, 120);
        };

        // Delegation
        container.addEventListener('mouseover', (e) => {
            const icon = e.target.closest('.badge-icon');
            if (!icon || !container.contains(icon)) return;
            if (hideTimeout) {
                clearTimeout(hideTimeout);
                hideTimeout = null;
            }
            show(icon);
        });

        container.addEventListener('mouseout', (e) => {
            const to = e.relatedTarget;
            // If moving to another badge inside the container, do nothing
            if (to && container.contains(to) && to.closest('.badge-icon')) return;
            hide();
        });

        // When mouse leaves container entirely
        container.addEventListener('mouseleave', hide);

        // Scroll/navigation safety
        window.addEventListener('scroll', hide, true);
    }

    handleNavClick(pageId) {
        if (pageId === 'editor') {
            this.loadScriptsList();
        }
        this.DOM.pages.forEach(page => page.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');

        this.DOM.navItems.forEach(item => item.classList.remove('active'));
        document.querySelector(`.nav-item[data-page="${pageId}"]`).classList.add('active');

        if (pageId === 'editor') {
            if (!this.monacoEditor) {
                this.initCodeEditor();           // create once visible
            } else {
                this.monacoEditor.layout();      // relayout if already created
            }
        }
        if (pageId === 'rpc') {
            this.initRpcTab();
        }
        if (pageId === 'settings') {
            this.initSettingsTab();
            this.initEmbedSettingsTab();
        }
    }

    showTokenModal(error = '') {
        this.DOM.tokenError.textContent = error;
        this.DOM.tokenModal.classList.add('visible');
    }

    hideTokenModal() {
        this.DOM.tokenModal.classList.remove('visible');
    }

    showMainInterface() {
        if (this.DOM.app.style.opacity === '1') return; // Prevent re-animation

        this.DOM.loadingScreen.style.opacity = '0';
        setTimeout(() => {
            this.DOM.loadingScreen.style.display = 'none';
            this.DOM.app.style.opacity = '1';

            // Initialize components that depend on external libraries HERE
            // to ensure everything is loaded and ready.
            this.initActivityDashboard();
            // The editor can also be initialized here if needed, or keep its lazy-loading logic.
            // this.initCodeEditor();

        }, 500);
    }

    handlePythonEvent(eventType, data) {
        console.log(`[Python Event] Type: ${eventType}`, data);
        switch (eventType) {
            case 'user_data_updated':
                this.updateUI(data);
                this.showMainInterface();
                break;
            case 'command_used':
                this.addActivityLog(`Used Command: <span class="highlight">${data.command}</span> in ${data.channel}.`);
                break;
            case 'ping_received':
                let link = '';
                if (data.channel_id && data.message_id) {
                    const guildPart = data.guild_id ? data.guild_id : '@me';
                    const appUrl = `discord://-/channels/${guildPart}/${data.channel_id}/${data.message_id}`;
                    const webUrl = `https://discord.com/channels/${guildPart}/${data.channel_id}/${data.message_id}`;
                    // Use pywebview API to open discord:// link to avoid browser prompt
                    link = ` <a href="#" onclick="window.pywebview.api.open_url('${appUrl}'); return false;" title="Open in App" style="color: var(--accent-cyan); text-decoration: none; font-size: 0.9em; margin-left: 5px;">(App)</a> <a href="#" onclick="window.pywebview.api.open_url('${webUrl}'); return false;" title="Open in Browser" style="color: var(--text-secondary); text-decoration: none; font-size: 0.8em;">(Web)</a>`;
                }
                this.addActivityLog(`Received Ping from: <span class="highlight">${data.user}</span> in <span class="highlight">${data.server_name}</span>${link}<br><span class="log-message-content">${data.content}</span>`);
                break;
            case 'friend_request':
                this.addActivityLog(`Friend Request from: <span class="highlight">${data.user}</span>`);
                break;
            case 'friend_added':
                this.addActivityLog(`Added Friend: <span class="highlight">${data.user}</span>`);
                break;
            case 'friend_request_sent':
                this.addActivityLog(`Sent Friend Request to: <span class="highlight">${data.user}</span>`);
                break;
            case 'server_joined':
                let serverLink = '';
                if (data.guild_id) {
                    const appUrl = `discord://-/channels/${data.guild_id}`;
                    const webUrl = `https://discord.com/channels/${data.guild_id}`;
                    // Use pywebview API to open discord:// link to avoid browser prompt
                    serverLink = ` <a href="#" onclick="window.pywebview.api.open_url('${appUrl}'); return false;" title="Open in App" style="color: var(--accent-cyan); text-decoration: none; font-size: 0.9em; margin-left: 5px;">(App)</a> <a href="#" onclick="window.pywebview.api.open_url('${webUrl}'); return false;" title="Open in Browser" style="color: var(--text-secondary); text-decoration: none; font-size: 0.8em;">(Web)</a>`;
                }
                this.addActivityLog(`Joined Server: <span class="highlight">${data.server_name}</span>${serverLink}`);
                break;
            case 'server_left':
                this.addActivityLog(`Left/kick Server: <span class="highlight">${data.server_name}</span>`);
                break;
            case 'friend_removed':
                this.addActivityLog(`Removed Friend: <span class="highlight">${data.user}</span>`);
                break;
            case 'role_added':
                this.addActivityLog(`Role Added: <span class="highlight">${data.role_name}</span> in <span class="highlight">${data.server_name}</span>`);
                break;
            case 'role_removed':
                this.addActivityLog(`Role Removed: <span class="highlight">${data.role_name}</span> in <span class="highlight">${data.server_name}</span>`);
                break;
            case 'startup_progress':
                this.updateLoadingStatus(data.message);
                break;
            case 'script_output':
                this.appendToConsole(data.content, 'output');
                break;
            case 'script_error':
                this.appendToConsole(data.error, 'error');
                break;
            case 'script_start':
                this.appendToConsole(`\n--- Running ${data.filename} ---`, 'system');
                this.setScriptRunningState(data.filename, true);
                break;
            case 'script_end':
                this.appendToConsole(`--- Finished ${data.filename} ---`, 'system');
                this.setScriptRunningState(data.filename, false);
                break;
            case 'sniper_log':
                let statusColor = 'var(--text-secondary)';
                if (data.status === 'claimed') statusColor = 'var(--accent-green)';
                else if (data.status === 'invalid') statusColor = 'var(--accent-red)';
                else if (data.status === 'ratelimited') statusColor = 'var(--accent-orange)';

                this.addActivityLog(`Nitro Sniper: <span style="color:${statusColor}">${data.status.toUpperCase()}</span> code <span class="highlight">${data.code}</span> in ${data.time}`);
                break;
            default:
                if (window.handleBotEvent) window.handleBotEvent(eventType, data);
        }
    }

    updateUI(data) {
        // Update user profile
        this.DOM.avatarImg.src = data.avatar;
        this.DOM.userName.textContent = data.username;
        this.DOM.userId.textContent = data.discriminator !== '0' ? `#${data.discriminator}` : '';
        this.DOM.userInfoNitro.textContent = data.nitro_type;
        this.DOM.userIdInfo.textContent = data.id;

        // Update dashboard stats
        this.DOM.serverCount.textContent = data.server_count;
        this.DOM.friendCount.textContent = data.friend_count;

        this.updateBadges(data.badges);
        this.startUptime();
    }

    updateBadges(badges) {
        const container = this.DOM.userInfoBadges;
        container.innerHTML = '';
        if (!badges || !Array.isArray(badges)) return;

        badges.forEach(badge => {
            const wrapper = document.createElement('div');
            wrapper.className = 'badge-icon';

            // Normalizes spaces in the badge name to avoid line breaks
            const normalizedName = badge.name.replace(/\s+/g, ' ').trim();
            wrapper.dataset.tip = normalizedName;       // ← tooltip text
            wrapper.setAttribute('aria-label', normalizedName);

            wrapper.innerHTML = `
            <img src="${badge.image}" alt="${normalizedName}" onerror="this.style.display='none'">
            `;
            container.appendChild(wrapper);
        });
    }

    updateLoadingStatus(text) {
        if (this.DOM.loadingStatus) {
            this.DOM.loadingStatus.textContent = text;
        }

        // Simulated progress logic based on text
        const progressBar = document.getElementById('loadingProgressBar');
        if (!progressBar) return;

        let progress = 10;
        const lower = text.toLowerCase();

        if (lower.includes('connecting')) progress = 30;
        else if (lower.includes('logged in')) progress = 50;
        else if (lower.includes('fetching')) progress = 65;
        else if (lower.includes('checking nitro')) progress = 75;
        else if (lower.includes('client badges')) progress = 85;
        else if (lower.includes('public profile')) progress = 90;
        else if (lower.includes('finalizing')) progress = 100;

        progressBar.style.width = `${progress}%`;
    }

    startUptime() {
        const el = this.DOM.uptime;
        if (!el || el.dataset.running) return;
        el.dataset.running = 'true';
        const startTime = Date.now();
        setInterval(() => {
            const elapsed = Date.now() - startTime;
            const h = String(Math.floor(elapsed / 3600000)).padStart(2, '0');
            const m = String(Math.floor((elapsed % 3600000) / 60000)).padStart(2, '0');
            const s = String(Math.floor((elapsed % 60000) / 1000)).padStart(2, '0');
            el.textContent = `${h}:${m}:${s}`;
        }, 1000);
    }

    addActivityLog(message) {
        const item = document.createElement('div');
        item.className = 'activity-log-item';
        const timestamp = new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        item.innerHTML = `
            <span class="log-timestamp">[${timestamp}]</span>
            <span class="log-message">${message}</span>
        `;
        const log = this.DOM.activityLog;
        // Add new notification at the top
        log.insertBefore(item, log.firstChild);
        // Limit to 100 logs (optional)
        while (log.childNodes.length > 100) {
            log.removeChild(log.lastChild);
        }
        // Auto scroll to top
        log.scrollTop = 0;
    }

    // ------------------ INIT MONACO / EDITOR ------------------
    initCodeEditor() {
        window.monacoReady.then(monaco => {
            this.monaco = monaco;
            if (!monaco) {
                console.error('[Editor] Monaco not available');
                return;
            }

            this.editorReady = true;

            this.configureMonacoPerformance(monaco);
            this.setupResizeObserver();

            // "New script" button
            if (this.DOM.newScriptBtn) {
                this.DOM.newScriptBtn.onclick = () => this.createNewScript();
            }

            // Click in wrapper = focus editor
            if (this.DOM.codeEditorWrapper) {
                this.DOM.codeEditorWrapper.addEventListener('click', () => this.focusEditor());
            }

            // Load scripts list
            this.loadScriptsList();
        });
    }

    configureMonacoPerformance(monaco) {
        monaco.editor.setTheme('vs-dark');

        const defaultOptions = {
            minimap: {
                enabled: true,
                maxColumn: 80,
                renderCharacters: false,
                showSlider: 'always'
            },
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
            lineNumbersMinChars: 3,
            fontSize: 14,
            fontFamily: "'Fira Code', 'Consolas', 'Monaco', monospace",
            fontLigatures: true,
            tabSize: 4,
            insertSpaces: true,
            cursorBlinking: 'blink',
            cursorSmoothCaretAnimation: true,
            smoothScrolling: true,
            quickSuggestions: true,
            suggestOnTriggerCharacters: true,
            acceptSuggestionOnEnter: 'on',
            tabCompletion: 'on',
            wordBasedSuggestions: true,
            parameterHints: { enabled: true },
            autoClosingBrackets: 'always',
            autoClosingQuotes: 'always',
            formatOnPaste: true,
            formatOnType: true,
            mouseWheelZoom: false,
            multiCursorModifier: 'ctrlCmd',
            accessibilitySupport: 'auto'
        };

        this.defaultEditorOptions = defaultOptions;

        // Python Snippets
        monaco.languages.registerCompletionItemProvider('python', {
            provideCompletionItems: () => {
                const k = monaco.languages.CompletionItemKind.Keyword;
                const r = monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet;
                return {
                    suggestions: [
                        {
                            label: 'def',
                            kind: k,
                            insertText: 'def ${1:function_name}(${2:args}):\n\t${3:pass}',
                            insertTextRules: r,
                            documentation: 'Define a function'
                        },
                        {
                            label: 'class',
                            kind: k,
                            insertText: 'class ${1:ClassName}:\n\t${2:pass}',
                            insertTextRules: r,
                            documentation: 'Define a class'
                        },
                        {
                            label: 'if',
                            kind: k,
                            insertText: 'if ${1:condition}:\n\t${2:pass}',
                            insertTextRules: r,
                            documentation: 'If statement'
                        },
                        {
                            label: 'for',
                            kind: k,
                            insertText: 'for ${1:item} in ${2:iterable}:\n\t${3:pass}',
                            insertTextRules: r,
                            documentation: 'For loop'
                        },
                        {
                            label: 'while',
                            kind: k,
                            insertText: 'while ${1:condition}:\n\t${2:pass}',
                            insertTextRules: r,
                            documentation: 'While loop'
                        },
                        {
                            label: 'try',
                            kind: k,
                            insertText: 'try:\n\t${1:pass}\nexcept ${2:Exception} as e:\n\t${3:pass}',
                            insertTextRules: r,
                            documentation: 'Try-except block'
                        },
                        {
                            label: 'import',
                            kind: k,
                            insertText: 'import ${1:module}',
                            insertTextRules: r,
                            documentation: 'Import module'
                        },
                        {
                            label: 'from',
                            kind: k,
                            insertText: 'from ${1:module} import ${2:name}',
                            insertTextRules: r,
                            documentation: 'Import from module'
                        }
                    ]
                };
            }
        });

        console.log('[Editor] Monaco configured');
    }

    setupResizeObserver() {
        if (typeof ResizeObserver !== 'undefined') {
            this.resizeObserver = new ResizeObserver(() => {
                if (this.monacoEditor) {
                    try {
                        this.monacoEditor.layout();
                    } catch (e) {
                        console.warn('Failed to layout editor:', e);
                    }
                }
            });

            if (this.DOM.codeEditorWrapper) {
                this.resizeObserver.observe(this.DOM.codeEditorWrapper);
            }
        }

        window.addEventListener('resize', () => {
            if (this.monacoEditor) {
                clearTimeout(this.resizeTimeout);
                this.resizeTimeout = setTimeout(() => {
                    this.monacoEditor.layout();
                }, 100);
            }
        });
    }

    // ------------------ SCRIPTS LIST (SIDEBAR) ------------------

    async loadScriptsList() {
        if (!this.DOM.scriptsList) return;

        if (!window.pywebview?.api?.list_scripts) {
            console.warn('[Editor] list_scripts not available');
            this.renderScriptsList();
            return;
        }

        try {
            const backendScripts = await window.pywebview.api.list_scripts();
            this.scripts = backendScripts.map(s => ({
                name: s.name,
                path: s.path,
                content: null,            // lazy-load
                model: null,
                isDirty: false,
                lastSavedContent: null,
                modelListener: null
            }));
            this.renderScriptsList();
        } catch (e) {
            console.error('[Editor] Failed to load scripts from backend:', e);
        }
    }

    renderScriptsList() {
        const list = this.DOM.scriptsList;
        if (!list) return;

        list.innerHTML = '';

        this.scripts.forEach(script => {
            const li = document.createElement('li');
            li.className = 'sidebar-script-item';
            if (!script.path) li.classList.add('unsaved');
            if (script.running) li.classList.add('running');

            const nameSpan = document.createElement('span');
            nameSpan.className = 'sidebar-script-name';
            nameSpan.style.flex = '1';
            let displayName = script.name + (script.isDirty ? ' *' : '');

            // Add running indicator if needed
            if (script.running) {
                // We'll use CSS for the dot via .running class, or append a span
                // Let's append a span for better control
                displayName += ' ▶';
            }
            nameSpan.textContent = displayName;
            nameSpan.title = script.path || 'Unsaved script';
            nameSpan.style.cursor = 'pointer';
            nameSpan.onclick = (e) => {
                e.stopPropagation();
                this.openScript(script);
            };

            const menuBtn = document.createElement('button');
            menuBtn.className = 'sidebar-script-menu';
            menuBtn.title = 'More actions';
            menuBtn.innerHTML = `
                <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                <circle cx="12" cy="5.5" r="1.7"/>
                <circle cx="12" cy="12" r="1.7"/>
                <circle cx="12" cy="18.5" r="1.7"/>
                </svg>
            `;
            menuBtn.onclick = (e) => {
                e.stopPropagation();
                this.showScriptContextMenu(script, li, nameSpan, menuBtn);
            };

            li.appendChild(nameSpan);
            li.appendChild(menuBtn);
            list.appendChild(li);
        });

        const oldMenu = document.getElementById('sidebar-script-context-menu');
        if (oldMenu) oldMenu.remove();
    }

    showScriptContextMenu(script, li, nameSpan, triggerEl) {
        const menu = document.createElement('ul');
        menu.id = 'sidebar-script-context-menu';
        menu.className = 'context-menu';

        const addItem = (text, action, disabled = false) => {
            const item = document.createElement('li');
            item.textContent = text;
            if (disabled) {
                item.classList.add('disabled');
            } else {
                item.onclick = () => {
                    action();
                    menu.remove();
                };
            }
            menu.appendChild(item);
        };

        addItem('Rename', () => this.startSidebarRename(script, li, nameSpan));
        addItem('Reveal in Explorer', () => this.revealScript(script), !script.path);
        addItem('Delete', () => this.deleteScript(script));

        document.body.appendChild(menu);

        const anchor = triggerEl || nameSpan;
        const rect = anchor.getBoundingClientRect();

        menu.style.top = `${rect.bottom}px`;
        menu.style.left = `${rect.left}px`;

        const close = (ev) => {
            if (!menu.contains(ev.target)) {
                menu.remove();
                document.removeEventListener('click', close);
            }
        };
        setTimeout(() => document.addEventListener('click', close), 0);
    }

    createNewScript() {
        const baseName = 'untitled';
        let idx = 1;
        let candidate;

        do {
            candidate = `${baseName}${idx > 1 ? '_' + idx : ''}.py`;
            idx++;
        } while (this.scripts.some(s => s.name === candidate));

        const script = {
            name: candidate,
            path: null,
            content: '# New script\n',
            model: null,
            isDirty: true,
            lastSavedContent: '',
            modelListener: null
        };

        this.scripts.push(script);
        this.renderScriptsList();
        this.openScript(script);
    }

    createNewScriptTab() {
        return this.createNewScript();
    }

    // ------------------ OPEN / TABS / MONACO ------------------

    async openScript(script) {
        if (!this.editorReady || !this.monaco) return;

        // Load from backend if needed
        if (script.content == null && script.path && window.pywebview?.api?.load_script) {
            try {
                const text = await window.pywebview.api.load_script(script.path);
                script.content = typeof text === 'string' ? text : '';
                script.lastSavedContent = script.content;
            } catch (e) {
                console.error('[Editor] Failed to read script:', e);
                script.content = script.content || '';
                script.lastSavedContent = script.lastSavedContent ?? script.content;
            }
        }

        let tabIndex = this.openTabs.findIndex(t =>
            t === script ||
            (t.path && script.path && t.path === script.path) ||
            (!t.path && !script.path && t.name === script.name)
        );

        if (tabIndex === -1) {
            this.openTabs.push(script);
            tabIndex = this.openTabs.length - 1;
        }

        this.activateTab(tabIndex);
    }

    ensureScriptModel(script) {
        if (!this.monaco || !this.monaco.editor) return;

        if (!script.model) {
            const content = script.content ?? '';
            script.model = this.monaco.editor.createModel(content, 'python');
            script.lastSavedContent = script.lastSavedContent ?? content;

            if (script.modelListener) {
                script.modelListener.dispose();
            }

            script.modelListener = script.model.onDidChangeContent(() => {
                const value = script.model.getValue();
                script.content = value;
                script.isDirty = (script.lastSavedContent ?? '') !== value;
                this.renderTabs();
                this.renderScriptsList();
            });
        }
    }

    attachEditorToScript(script) {
        if (!this.monaco) return;
        if (!script.model) this.ensureScriptModel(script);

        if (!this.monacoEditor) {
            const baseOptions = this.defaultEditorOptions ? { ...this.defaultEditorOptions } : {};
            this.monacoEditor = this.monaco.editor.create(this.DOM.codeEditorWrapper, {
                ...baseOptions,
                model: script.model
            });
        } else {
            this.monacoEditor.setModel(script.model);
        }
    }

    renderTabs() {
        const tabsContainer = this.DOM.editorTabs;
        if (!tabsContainer) return;

        tabsContainer.innerHTML = '';

        this.openTabs.forEach((script, index) => {
            const li = document.createElement('li');
            li.className = 'editor-tab';
            if (index === this.activeTabIndex) li.classList.add('active');
            if (script.isDirty) li.classList.add('unsaved');

            const titleSpan = document.createElement('span');
            titleSpan.className = 'editor-tab-title';
            titleSpan.textContent = script.name + (script.isDirty ? ' *' : '');
            titleSpan.onclick = () => this.activateTab(index);

            const closeBtn = document.createElement('button');
            closeBtn.className = 'editor-tab-close';
            closeBtn.innerHTML = '<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"></path></svg>';
            closeBtn.onclick = (e) => {
                e.stopPropagation();
                this.closeTab(index);
            };

            li.appendChild(titleSpan);
            li.appendChild(closeBtn);
            tabsContainer.appendChild(li);
        });
    }

    activateTab(index) {
        if (index < 0 || index >= this.openTabs.length) return;
        this.activeTabIndex = index;

        const script = this.openTabs[index];
        this.ensureScriptModel(script);
        this.attachEditorToScript(script);
        this.renderTabs();
        this.updateScriptButtons();
        this.focusEditor();
    }

    async closeTab(index, options = {}) {
        if (index < 0 || index >= this.openTabs.length) return;

        const script = this.openTabs[index];

        if (!options.skipConfirm && script.isDirty) {
            let ok;
            if (typeof this.showConfirmModal === 'function') {
                ok = await this.showConfirmModal(
                    'Close Tab',
                    `Close "${script.name}" without saving?`
                );
            } else {
                ok = window.confirm(`Close "${script.name}" without saving?`);
            }
            if (!ok) return;
        }

        this.openTabs.splice(index, 1);

        if (this.activeTabIndex === index) {
            if (this.openTabs.length === 0) {
                this.activeTabIndex = -1;
                if (this.monacoEditor) {
                    this.monacoEditor.setModel(null);
                }
            } else {
                const newIndex = index >= this.openTabs.length ? this.openTabs.length - 1 : index;
                this.activateTab(newIndex);
            }
        } else if (this.activeTabIndex > index) {
            this.activeTabIndex--;
        }

        this.renderTabs();
    }

    focusEditor() {
        if (this.monacoEditor) {
            requestAnimationFrame(() => {
                try {
                    this.monacoEditor.focus();
                    this.monacoEditor.layout();
                } catch (e) {
                    console.warn('[Editor] Failed to focus editor:', e);
                }
            });
        }
    }

    // ------------------ SCRIPT EXECUTION ------------------

    async runCurrentScript() {
        if (this.activeTabIndex === -1 || !this.openTabs[this.activeTabIndex]) {
            this.showNotification("No script open to run.", 'error');
            return;
        }

        const script = this.openTabs[this.activeTabIndex];
        let content = "";

        if (this.monacoEditor && this.activeTabIndex !== -1) {
            content = this.monacoEditor.getValue();
        } else {
            content = script.content;
        }

        if (script.isDirty) {
            await this.saveActiveScript();
        }

        this.showNotification(`Running ${script.name}...`, 'info');

        window.pywebview.api.run_script_content(script.name, content).then(res => {
            if (!res.success) {
                this.appendToConsole("Failed to start script: " + res.error, 'error');
            }
        }).catch(e => {
            console.error("Error calling run_script_content:", e);
            this.appendToConsole("Error communicating with backend to run script.", 'error');
        });
    }

    stopCurrentScript() {
        const script = this.scripts[this.activeTabIndex];
        if (!script) return;

        if (window.pywebview && window.pywebview.api.stop_script_content) {
            window.pywebview.api.stop_script_content(script.name).then(() => {
                this.appendToConsole(`[Request] Stopping ${script.name}...`, 'system');
            });
        }
    }

    setScriptRunningState(filename, isRunning) {
        // Update global script list
        const script = this.scripts.find(s => s.name === filename);
        if (script) {
            script.running = isRunning;
            // Force re-render of sidebar to show/hide indicators
            this.renderScriptsList();
        }

        // If the updated script is the active one, update buttons immediately
        const activeScript = this.openTabs[this.activeTabIndex];
        if (activeScript && activeScript.name === filename) {
            this.updateScriptButtons();
        }
    }

    updateScriptButtons() {
        const script = this.scripts[this.activeTabIndex];
        const isRunning = script ? !!script.running : false;

        if (this.DOM.runScriptBtn) {
            this.DOM.runScriptBtn.style.display = isRunning ? 'none' : 'flex';
        }
        if (this.DOM.stopScriptBtn) {
            this.DOM.stopScriptBtn.style.display = isRunning ? 'flex' : 'none';
        }
    }

    appendToConsole(text, type = 'output') {
        const consoleOut = this.DOM.consoleOutput;
        if (!consoleOut) return;

        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;

        const time = new Date().toLocaleTimeString();

        if (type === 'system') {
            entry.innerText = `[${time}] ${text}`;
        } else if (type === 'error') {
            entry.innerText = `[${time}] Error:\n${text}`;
        } else {
            entry.innerText = text;
        }

        consoleOut.appendChild(entry);
        consoleOut.scrollTop = consoleOut.scrollHeight;
    }

    clearConsole() {
        if (this.DOM.consoleOutput) this.DOM.consoleOutput.innerHTML = '';
    }

    // ------------------ RENAME ------------------

    validateScriptName(name, originalName) {
        if (!name || name.trim() === '') {
            return { isValid: false, name: null, error: 'The name cannot be empty' };
        }

        const cleanName = name.trim();
        const invalidChars = /[<>:"/\\|?*]/;
        if (invalidChars.test(cleanName)) {
            return {
                isValid: false,
                name: null,
                error: 'The name contains invalid characters: < > : " / \\ | ? *'
            };
        }

        const reservedNames = [
            'con', 'prn', 'aux', 'nul',
            'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
            'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        ];
        const baseName = cleanName.toLowerCase();

        if (reservedNames.includes(baseName) || reservedNames.includes(baseName.replace('.py', ''))) {
            return {
                isValid: false,
                name: null,
                error: 'This name is reserved and cannot be used'
            };
        }

        if (cleanName.startsWith(' ') || cleanName.endsWith(' ') ||
            cleanName.startsWith('.') || cleanName.endsWith('.')) {
            return {
                isValid: false,
                name: null,
                error: 'The name cannot start or end with a space or a dot'
            };
        }

        let finalName = cleanName;
        if (!finalName.toLowerCase().endsWith('.py')) {
            finalName += '.py';
        }

        if (finalName.length > 250) {
            return {
                isValid: false,
                name: null,
                error: 'The script name is too long (max 250 characters)'
            };
        }

        const nameConflict = this.scripts.some(s =>
            s.name === finalName && s.name !== originalName
        );

        if (nameConflict) {
            return {
                isValid: false,
                name: null,
                error: 'A script with this name already exists'
            };
        }

        return { isValid: true, name: finalName, error: null };
    }

    startSidebarRename(script, li, nameSpan) {
        const input = document.createElement('input');
        input.type = 'text';
        input.value = script.name.replace(/\.py$/, '');
        input.className = 'sidebar-script-rename-input';
        input.style.fontFamily = 'inherit';
        input.style.fontSize = 'inherit';
        input.style.fontWeight = 'inherit';
        input.style.color = 'inherit';
        input.style.background = 'inherit';
        input.style.border = '1px solid #00BFFF';
        input.style.borderRadius = '4px';
        input.style.outline = 'none';
        input.style.padding = '2px 6px';
        input.style.margin = '0';
        input.style.width = Math.max(120, script.name.length * 8) + 'px';
        input.style.boxSizing = 'border-box';

        nameSpan.replaceWith(input);
        input.focus();
        input.select();

        const finish = async (save) => {
            if (!save) {
                this.renderScriptsList();
                return;
            }

            const rawName = input.value.trim();
            const validation = this.validateScriptName(rawName, script.name);

            if (!validation.isValid) {
                this.showNotification?.(validation.error, 'error');
                this.renderScriptsList();
                return;
            }

            const newName = validation.name;
            if (newName === script.name) {
                this.renderScriptsList();
                return;
            }

            try {
                await this.renameScript(script, newName);
            } catch (e) {
                console.error('[Editor] Rename failed:', e);
                this.showNotification?.('Error while renaming script', 'error');
            } finally {
                this.renderScriptsList();
                this.renderTabs();
            }
        };

        input.onblur = () => finish(true);
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                finish(true);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                finish(false);
            }
        };

        input.oncontextmenu = (e) => e.preventDefault();
    }

    async renameScript(script, newName) {
        const oldPath = script.path;
        let newPath = null;

        if (oldPath) {
            const idx = Math.max(oldPath.lastIndexOf('/'), oldPath.lastIndexOf('\\'));
            newPath = idx === -1 ? newName : oldPath.slice(0, idx + 1) + newName;

            if (!window.pywebview?.api?.rename_script) {
                throw new Error('Backend rename_script not available');
            }

            const ok = await window.pywebview.api.rename_script(oldPath, newPath);
            if (!ok) {
                throw new Error('Backend failed to rename file');
            }

            script.path = newPath;
        }

        script.name = newName;
        // openTabs pointe sur les mêmes objets => tabs MAJ automatiquement
    }

    // ------------------ DELETE / REVEAL / SAVE ------------------

    async deleteScript(script) {
        // Custom confirmation
        let ok;
        if (typeof this.showConfirmModal === 'function') {
            ok = await this.showConfirmModal(
                'Delete Script',
                `Are you sure you want to delete "${script.name}" ? This action cannot be undone.`
            );
        } else {
            ok = window.confirm(`Delete "${script.name}" ?`);
        }

        if (!ok) return;

        // Delete from disk
        if (script.path && window.pywebview?.api?.delete_script) {
            try {
                const success = await window.pywebview.api.delete_script(script.path);
                if (!success) {
                    this.showNotification?.('Error while deleting script on disk', 'error');
                    return;
                }
            } catch (e) {
                console.error('[Editor] Failed to delete file on disk:', e);
                this.showNotification?.('Error while deleting script on disk', 'error');
                return;
            }
        }

        // Close tab if open (without asking for confirmation again)
        const tabIndex = this.openTabs.indexOf(script);
        if (tabIndex !== -1) {
            await this.closeTab(tabIndex, { skipConfirm: true });
        }

        // Remove from list
        this.scripts = this.scripts.filter(s => s !== script);

        this.renderScriptsList();
        this.renderTabs();
    }

    async revealScript(script) {
        if (!script.path) {
            this.showNotification?.('Script must be saved before reveal', 'info');
            return;
        }

        if (!window.pywebview?.api?.reveal_in_explorer) {
            console.warn('[Editor] reveal_in_explorer not available');
            return;
        }

        try {
            await window.pywebview.api.reveal_in_explorer(script.path);
        } catch (e) {
            console.error('[Editor] Failed to reveal file:', e);
            this.showNotification?.('Error while opening file location', 'error');
        }
    }

    async saveActiveScript() {
        if (this.activeTabIndex < 0 || this.activeTabIndex >= this.openTabs.length) return;
        const script = this.openTabs[this.activeTabIndex];
        if (!script || !script.model) return;

        if (!window.pywebview?.api?.save_script) {
            console.warn('[Editor] save_script not available');
            return;
        }

        const content = script.model.getValue();
        const path = script.path || `scripts/${script.name}`;

        try {
            const ok = await window.pywebview.api.save_script(path, content);
            if (!ok) {
                this.showNotification?.('Failed to save script', 'error');
                return;
            }

            script.path = path;
            script.lastSavedContent = content;
            script.isDirty = false;

            this.renderTabs();
            this.renderScriptsList();
        } catch (e) {
            console.error('[Editor] save_script failed:', e);
            this.showNotification?.('Failed to save script', 'error');
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `editor-notification editor-notification-${type}`;
        notification.textContent = message;
        notification.style.position = 'fixed';
        notification.style.bottom = '20px';
        notification.style.right = '20px';
        notification.style.zIndex = '10000';
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(20px)';
        notification.style.transition = 'all 0.3s ease';

        document.body.appendChild(notification);

        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        });

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(20px)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    showConfirmModal(title, message, options = {}) {
        const {
            confirmLabel = 'Confirm',
            cancelLabel = 'Cancel',
            danger = false   // for delete, set danger = true if needed
        } = options;

        return new Promise((resolve) => {
            // --- Backdrop ---
            const backdrop = document.createElement('div');
            backdrop.className = 'confirm-modal-backdrop';
            backdrop.style.cssText = `
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.65);
                backdrop-filter: blur(10px);
                z-index: 2147483646;
                opacity: 0;
                transition: opacity 0.2s ease-out;
            `;

            // --- Modal ---
            const modal = document.createElement('div');
            modal.className = 'confirm-modal';
            modal.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%) scale(0.95);
                background: rgba(255, 255, 255, 0.03);
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                padding: 1.75rem 2rem;
                min-width: 340px;
                max-width: 460px;
                box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
                z-index: 2147483647;
                opacity: 0;
                transition: all 0.2s ease-out;
            `;

            modal.innerHTML = `
                <div class="confirm-modal-title" style="
                    font-size: 1.3rem;
                    font-weight: 600;
                    color: var(--accent-cyan, #00BFFF);
                    margin-bottom: 0.75rem;
                    text-align: left;
                ">
                    ${title}
                </div>
                <div class="confirm-modal-message" style="
                    font-size: 0.95rem;
                    color: var(--text-primary, #e5f3ff);
                    line-height: 1.5;
                    margin-bottom: 1.5rem;
                    opacity: 0.9;
                ">
                    ${message}
                </div>
                <div class="confirm-modal-actions" style="
                    display: flex;
                    justify-content: flex-end;
                    gap: 0.75rem;
                ">
                    <button class="confirm-modal-btn cancel" style="
                        padding: 0.55rem 1.4rem;
                        border-radius: 6px;
                        border: 1px solid rgba(255,255,255,0.2);
                        background: rgba(255,255,255,0.04);
                        color: var(--text-secondary, #c8d7ff);
                        font-size: 0.9rem;
                        cursor: pointer;
                        outline: none;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        gap: 0.4rem;
                        transition: all 0.15s ease-out;
                    ">
                        ${cancelLabel}
                    </button>
                    <button class="confirm-modal-btn confirm" style="
                        padding: 0.55rem 1.4rem;
                        border-radius: 6px;
                        border: none;
                        background: ${danger ? '#ff4b5c' : 'var(--accent-cyan, #00BFFF)'};
                        color: #fff;
                        font-size: 0.9rem;
                        cursor: pointer;
                        outline: none;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        gap: 0.4rem;
                        box-shadow: 0 0 14px ${danger ? 'rgba(255,75,92,0.55)' : 'rgba(0,191,255,0.55)'};
                        transition: all 0.15s ease-out;
                    ">
                        ${confirmLabel}
                    </button>
                </div>
            `;

            document.body.appendChild(backdrop);
            document.body.appendChild(modal);

            const cancelBtn = modal.querySelector('.confirm-modal-btn.cancel');
            const confirmBtn = modal.querySelector('.confirm-modal-btn.confirm');

            // Small entry animation
            requestAnimationFrame(() => {
                backdrop.style.opacity = '1';
                modal.style.opacity = '1';
                modal.style.transform = 'translate(-50%, -50%) scale(1)';
            });

            const cleanup = (value) => {
                // exit animation
                backdrop.style.opacity = '0';
                modal.style.opacity = '0';
                modal.style.transform = 'translate(-50%, -50%) scale(0.95)';

                setTimeout(() => {
                    backdrop.remove();
                    modal.remove();
                }, 180);

                document.removeEventListener('keydown', onKeyDown);
                resolve(value);
            };

            const onKeyDown = (e) => {
                if (e.key === 'Escape') {
                    cleanup(false);
                } else if (e.key === 'Enter') {
                    cleanup(true);
                }
            };

            cancelBtn.addEventListener('click', () => cleanup(false));
            confirmBtn.addEventListener('click', () => cleanup(true));

            // click outside => cancel
            backdrop.addEventListener('click', (e) => {
                if (e.target === backdrop) {
                    cleanup(false);
                }
            });

            document.addEventListener('keydown', onKeyDown);
        });
    }

    async start() {
        console.log("▶️ Starting handshake with backend...");
        try {
            // 1. Get Config first
            let config = await window.pywebview.api.get_config();

            // 2. Apply Background
            if (config && config.ui && config.ui.background_file) {
                try {
                    const bgPath = config.ui.background_file.trim();
                    if (bgPath.startsWith('http://') || bgPath.startsWith('https://')) {
                        document.body.style.backgroundImage = `url('${bgPath}')`;
                    } else {
                        if (window.pywebview.api.get_local_image) {
                            const imgRes = await window.pywebview.api.get_local_image(bgPath);
                            if (imgRes.success) {
                                document.body.style.backgroundImage = `url('${imgRes.data}')`;
                            }
                        }
                    }
                } catch (e) {
                    console.error("BG Load Error:", e);
                }
            }

            this.initTooltipDelegation();

            // 3. Logic: Check tokens BEFORE login
            const userToken = config.discord.token;
            const controllerToken = config.discord.controller_token;

            console.log("🔍 Checking config before login...");

            if (userToken) {
                if (!controllerToken) {
                    console.log("⚠️ User found, but Controller missing. Prompting...");
                    this.tempUserToken = userToken;
                    // Force the controller modal to show. 
                    // Note: If 'try_initial_login' isn't called, backend waits.
                    this.showControllerModal();
                } else {
                    console.log("✅ All tokens present. Auto-Login.");
                    const result = await window.pywebview.api.try_initial_login();
                    if (result.success) {
                        // OK
                    } else {
                        this.showTokenModal(result.error);
                    }
                }
            } else {
                console.log("🚫 No User Token. Prompting...");
                this.showTokenModal();
            }

        } catch (e) {
            console.error("Fatal error during startup handshake:", e);
            this.showTokenModal("Backend connection failed.");
        }
    }

    async handleTokenSubmit() {
        const token = this.DOM.tokenInput.value;
        if (!token) {
            this.showTokenModal('Token cannot be empty.');
            return;
        }

        // Store token temporarily and move to Controller Setup
        this.tempUserToken = token;
        this.hideTokenModal();

        // Show Controller Modal immediately
        this.showControllerModal();
    }

    showControllerModal(error = '') {
        if (!this.DOM.controllerModal) return;
        this.DOM.controllerError.textContent = error;
        this.DOM.controllerModal.style.display = 'flex';
        // Force reflow
        void this.DOM.controllerModal.offsetWidth;
        this.DOM.controllerModal.classList.add('visible');
    }

    hideControllerModal() {
        if (!this.DOM.controllerModal) return;
        this.DOM.controllerModal.classList.remove('visible');
        setTimeout(() => {
            this.DOM.controllerModal.style.display = 'none';
        }, 300); // Wait for transition
    }

    async handleControllerSubmit() {
        const token = this.DOM.controllerTokenInput.value.trim();
        if (!token) {
            this.showControllerModal('Token cannot be empty.');
            return;
        }

        console.log("🔑 Saving Controller Token...");
        try {
            if (this.tempUserToken) {
                // Dual Setup Flow
                if (window.pywebview.api.setup_and_login) {
                    const result = await window.pywebview.api.setup_and_login(this.tempUserToken, token);
                    this.tempUserToken = null; // Clear temp token
                    if (result.success) {
                        this.hideControllerModal();
                    } else {
                        // If login fails, we might need to reset? 
                        // Show error on controller modal for now
                        this.showControllerModal(result.error || 'Login failed.');
                    }
                }
            } else {
                // Standalone Controller Update
                if (window.pywebview.api.save_controller_token) {
                    const result = await window.pywebview.api.save_controller_token(token);
                    if (result.success) {
                        this.hideControllerModal();
                    } else {
                        this.showControllerModal('Failed to save token.');
                    }
                }
            }
        } catch (e) {
            console.error("Error saving controller token:", e);
            this.showControllerModal('Error saving token.');
        }
    }

    async handleControllerSkip() {
        if (this.tempUserToken) {
            // User skipped controller setup during initial flow -> Just login with user token
            try {
                if (window.pywebview.api.setup_and_login) {
                    const result = await window.pywebview.api.setup_and_login(this.tempUserToken, null);
                    this.tempUserToken = null;
                    if (result.success) {
                        this.hideControllerModal();
                    } else {
                        // Fallback to token modal if user token was bad? 
                        // Or show error here.
                        this.showControllerModal(result.error || 'Login failed.');
                    }
                }
            } catch (e) {
                this.showControllerModal('Error during login.');
            }
        } else {
            // Just hide if standalone
            this.hideControllerModal();
        }
    }

    showControllerGuide() {
        if (this.DOM.controllerSetupView) this.DOM.controllerSetupView.style.display = 'none';
        if (this.DOM.controllerGuideView) this.DOM.controllerGuideView.style.display = 'block';
    }

    backToControllerSetup() {
        if (this.DOM.controllerGuideView) this.DOM.controllerGuideView.style.display = 'none';
        if (this.DOM.controllerSetupView) this.DOM.controllerSetupView.style.display = 'block';
    }

    // Tab Settings: Styled form to edit prefix and background
    async initSettingsTab() {
        const prefixInput = document.getElementById('commandPrefixInput');
        const bgInput = document.getElementById('backgroundFileInput');
        const saveBtn = document.getElementById('saveSettingsBtn');

        if (!prefixInput || !bgInput || !saveBtn) return;

        try {
            const config = await window.pywebview.api.get_config();

            // Populate fields
            prefixInput.value = config.discord.command_prefix || '';
            bgInput.value = config.ui.background_file || '';

            const platformSelect = document.getElementById('platformSelect');
            const savePlatformBtn = document.getElementById('savePlatformBtn');

            if (platformSelect) {
                platformSelect.value = config.discord.platform || 'desktop';
            }

            if (savePlatformBtn && platformSelect) {
                savePlatformBtn.onclick = async () => {
                    const newPlatform = platformSelect.value;
                    const oldPlatform = config.discord.platform || 'desktop';

                    savePlatformBtn.textContent = 'Saving...';
                    savePlatformBtn.disabled = true;

                    try {
                        const res = await window.pywebview.api.save_config({
                            'discord.platform': newPlatform
                        });

                        if (res && res.success) {
                            savePlatformBtn.textContent = 'Saved!';
                            // Update config local copy
                            config.discord.platform = newPlatform;

                            setTimeout(() => {
                                savePlatformBtn.textContent = 'Save';
                                savePlatformBtn.style.background = '';
                                savePlatformBtn.style.color = '';
                                savePlatformBtn.disabled = false;
                            }, 2000);
                        } else {
                            savePlatformBtn.textContent = 'Error';
                            setTimeout(() => {
                                savePlatformBtn.textContent = 'Save';
                                savePlatformBtn.disabled = false;
                            }, 2000);
                        }
                    } catch (e) {
                        console.error('Error saving platform:', e);
                        savePlatformBtn.textContent = 'Error';
                        setTimeout(() => {
                            savePlatformBtn.textContent = 'Save';
                            savePlatformBtn.disabled = false;
                        }, 2000);
                    }
                };
            }

            // Handle Save
            saveBtn.onclick = async () => {
                const newPrefix = prefixInput.value;
                const newBg = bgInput.value;
                const oldPrefix = config.discord.command_prefix;
                const oldBg = config.ui.background_file;

                // Visual feedback
                saveBtn.textContent = 'Saving...';
                saveBtn.disabled = true;

                try {
                    const res = await window.pywebview.api.save_config({
                        'discord.command_prefix': newPrefix,
                        'ui.background_file': newBg
                    });

                    if (res && res.success) {
                        saveBtn.textContent = 'Saved!';

                        // Update config local copy
                        config.discord.command_prefix = newPrefix;
                        config.ui.background_file = newBg;

                        setTimeout(() => {
                            saveBtn.textContent = 'Save';
                            saveBtn.style.background = '';
                            saveBtn.style.color = '';
                            saveBtn.disabled = false;
                        }, 2000);

                        // Apply background immediately if changed
                        if (newBg !== oldBg) {
                            let bgUrl = newBg.trim();
                            const isWeb = bgUrl.startsWith('http://') || bgUrl.startsWith('https://');

                            if (isWeb) {
                                document.body.style.backgroundImage = `url('${bgUrl}')`;
                            } else {
                                // Try loading local image via API
                                try {
                                    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_local_image) {
                                        const imgRes = await window.pywebview.api.get_local_image(bgUrl);
                                        if (imgRes.success) {
                                            document.body.style.backgroundImage = `url('${imgRes.data}')`;
                                        }
                                    }
                                } catch (e) {
                                    console.error("Error loading local image:", e);
                                }
                            }
                        }
                    } else {
                        saveBtn.textContent = 'Error';
                        setTimeout(() => {
                            saveBtn.textContent = 'Save';
                            saveBtn.disabled = false;
                        }, 2000);
                    }
                } catch (err) {
                    console.error('Error saving settings:', err);
                    saveBtn.textContent = 'Error';
                    setTimeout(() => {
                        saveBtn.textContent = 'Save';
                        saveBtn.disabled = false;
                    }, 2000);
                }
            };
        } catch (e) {
            console.error('Error loading settings:', e);
        }
    }

    // Embed Customization Settings with Modal and Live Preview
    async initEmbedSettingsTab() {
        const openBtn = document.getElementById('openEmbedEditorBtn');
        const modal = document.getElementById('embedEditorModal');
        const closeBtn = document.getElementById('closeEmbedEditorBtn');

        const authorIconInput = document.getElementById('embedAuthorIconInput');
        const authorTextInput = document.getElementById('embedAuthorTextInput');
        const thumbnailInput = document.getElementById('embedThumbnailInput');
        const footerIconInput = document.getElementById('embedFooterIconInput');
        const footerTextInput = document.getElementById('embedFooterTextInput');
        const colorInput = document.getElementById('embedColorInput');
        const colorPicker = document.getElementById('embedColorPicker');
        const saveBtn = document.getElementById('saveEmbedSettingsBtn');

        // Preview elements
        const previewCard = document.getElementById('embedPreviewCard');
        const previewAuthorIcon = document.getElementById('embedPreviewAuthorIcon');
        const previewAuthorName = document.getElementById('embedPreviewAuthorName');
        const previewBrandText = document.getElementById('embedPreviewBrandText');
        const previewThumbnail = document.getElementById('embedPreviewThumbnail');
        const previewFooterIcon = document.getElementById('embedPreviewFooterIcon');
        const previewFooterText = document.getElementById('embedPreviewFooterText');

        if (!openBtn || !modal) return;

        // Open modal
        openBtn.onclick = async () => {
            modal.style.display = 'flex';
            await this.loadEmbedSettings();
            this.updateEmbedPreview();
        };

        // Close modal
        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };

        // Close on backdrop click
        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = 'none';
        };

        // Live preview update function
        this.updateEmbedPreview = () => {
            // Update author icon
            if (authorIconInput.value) {
                previewAuthorIcon.style.display = 'block';
                previewAuthorIcon.src = authorIconInput.value;
            } else {
                previewAuthorIcon.style.display = 'none';
            }

            // Update brand text (author_text goes in description area)
            previewBrandText.textContent = authorTextInput.value || 'Orbyte';

            // Update thumbnail
            if (thumbnailInput.value) {
                previewThumbnail.style.display = 'block';
                previewThumbnail.src = thumbnailInput.value;
            } else {
                previewThumbnail.style.display = 'none';
            }

            // Update footer
            if (footerIconInput.value) {
                previewFooterIcon.style.display = 'block';
                previewFooterIcon.src = footerIconInput.value;
            } else {
                previewFooterIcon.style.display = 'none';
            }
            previewFooterText.textContent = footerTextInput.value || '# Orbyte Selfbot';

            // Update color (border-left)
            const hex = colorInput.value.replace('#', '');
            if (/^[0-9A-Fa-f]{6}$/.test(hex)) {
                previewCard.style.borderLeftColor = '#' + hex;
            }
        };

        // Load settings function
        this.loadEmbedSettings = async () => {
            try {
                const config = await window.pywebview.api.get_config();
                const embed = config.embed || {};

                if (authorIconInput) authorIconInput.value = embed.author_icon_url || '';
                if (authorTextInput) authorTextInput.value = embed.author_text || 'Orbyte';
                if (thumbnailInput) thumbnailInput.value = embed.thumbnail_url || '';
                if (footerIconInput) footerIconInput.value = embed.footer_icon_url || '';
                if (footerTextInput) footerTextInput.value = embed.footer_text || '# Orbyte Selfbot';
                if (colorInput) colorInput.value = embed.color || '2b2d31';
                if (colorPicker) colorPicker.value = '#' + (embed.color || '2b2d31');
            } catch (e) {
                console.error('Error loading embed settings:', e);
            }
        };

        // Sync color picker
        if (colorPicker && colorInput) {
            colorPicker.addEventListener('input', () => {
                colorInput.value = colorPicker.value.replace('#', '');
                this.updateEmbedPreview();
            });
        }

        // Live update on input change
        const allInputs = [authorIconInput, authorTextInput, thumbnailInput, footerIconInput, footerTextInput, colorInput];
        allInputs.forEach(input => {
            if (input) {
                input.addEventListener('input', () => this.updateEmbedPreview());
            }
        });

        // Handle Save
        if (saveBtn) {
            saveBtn.onclick = async () => {
                saveBtn.textContent = '💾 Saving...';
                saveBtn.disabled = true;

                try {
                    const embedData = {
                        author_icon_url: authorIconInput?.value || '',
                        author_text: authorTextInput?.value || 'Orbyte',
                        thumbnail_url: thumbnailInput?.value || '',
                        footer_icon_url: footerIconInput?.value || '',
                        footer_text: footerTextInput?.value || '# Orbyte Selfbot',
                        color: colorInput?.value?.replace('#', '') || '2b2d31'
                    };

                    const res = await window.pywebview.api.save_config({ 'embed': embedData });

                    if (res && res.success) {
                        saveBtn.textContent = '✅ Saved!';
                        setTimeout(() => {
                            saveBtn.textContent = '💾 Save Settings';
                            saveBtn.disabled = false;
                        }, 2000);
                    } else {
                        saveBtn.textContent = '❌ Error';
                        setTimeout(() => {
                            saveBtn.textContent = '💾 Save Settings';
                            saveBtn.disabled = false;
                        }, 2000);
                    }
                } catch (err) {
                    console.error('Error saving embed settings:', err);
                    saveBtn.textContent = '❌ Error';
                    setTimeout(() => {
                        saveBtn.textContent = '💾 Save Settings';
                        saveBtn.disabled = false;
                    }, 2000);
                }
            };
        }
    }

    initActivityDashboard() {
        if (!this.DOM.messagesChart) return;
        this.createCharts();

        // Track current range
        this.currentTimeRange = this.DOM.timeRangeSelector.value;

        this.DOM.timeRangeSelector.addEventListener('change', (e) => {
            this.currentTimeRange = e.target.value;
            this.updateCharts(this.currentTimeRange);
        });

        // Initial load
        this.updateCharts(this.currentTimeRange);

        // Auto-refresh every 60 seconds
        if (this.activityRefreshInterval) clearInterval(this.activityRefreshInterval);
        this.activityRefreshInterval = setInterval(() => {
            if (document.visibilityState === 'visible') {
                console.log("[Auto-Refresh] Updating activity charts...");
                this.updateCharts(this.currentTimeRange);
            }
        }, 60000); // 60s
    }

    createCharts() {
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false } // Titles are now in HTML
            },
            scales: {
                x: {
                    ticks: {
                        color: '#ddddddff',
                        maxRotation: 0,
                        autoSkip: true,
                        autoSkipPadding: 20
                    },
                    grid: { color: 'rgba(0, 191, 255, 0.1)' }
                },
                y: {
                    beginAtZero: true,
                    min: 0,
                    suggestedMax: 5, // Ensures grid doesn't look cramped with low data
                    ticks: {
                        color: '#ddddddff',
                        padding: 10,
                        stepSize: 1 // Integer steps for count data
                    },
                    grid: { color: 'var(--border-glow)' }
                }
            }
        };

        // Note: The 'label' is still useful for accessibility and potential tooltips.
        const chartConfigs = [
            { id: 'messagesChart', label: 'Messages Sent', borderColor: '#00BFFF' },
            { id: 'reactionsChart', label: 'Reactions Added', borderColor: '#39d47a' },
            { id: 'pingsChart', label: 'Pings Received', borderColor: '#ffba3c' },
            { id: 'serversChart', label: 'Servers Joined', borderColor: '#ff5a5a' }
        ];

        chartConfigs.forEach(config => {
            const ctx = this.DOM[config.id].getContext('2d');
            this.charts[config.id] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: config.label,
                        data: [],
                        borderColor: config.borderColor,
                        backgroundColor: `${config.borderColor}33`,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: chartOptions
            });
        });
    }

    async updateCharts(timeRange) {
        console.log(`📊 Fetching activity data for time range: ${timeRange}`);

        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_activity_history) {
            try {
                // Convert range to days (approx)
                let days = 7;
                if (timeRange === 'all') {
                    days = 3650; // 10 years
                } else {
                    const parsed = parseInt(timeRange, 10);
                    if (!isNaN(parsed)) {
                        days = parsed;
                    }
                }

                const res = await window.pywebview.api.get_activity_history(days);
                if (res.success && res.data) {
                    const d = res.data;
                    this.updateChartData('messagesChart', d.labels, d.messages);
                    this.updateChartData('reactionsChart', d.labels, d.reactions);
                    this.updateChartData('pingsChart', d.labels, d.pings);
                    this.updateChartData('serversChart', d.labels, d.servers);
                } else {
                    console.error("Failed to fetch activity history:", res.error);
                }
            } catch (e) {
                console.error("Error calling get_activity_history:", e);
            }
        } else {
            // Fallback if API not ready
            console.warn("Backend API not ready for activity history");
        }
    }

    updateChartData(chartId, labels, data) {
        if (this.charts[chartId]) {
            this.charts[chartId].data.labels = labels;
            this.charts[chartId].data.datasets[0].data = data;
            this.charts[chartId].update();
        }
    }

    // --- RPC TAB ---
    // --- RPC TAB ---
    async initRpcTab() {
        if (this.rpcInitialized) return;
        this.rpcInitialized = true;

        const DOM = {
            appId: document.getElementById('rpcAppId'),
            controllerStatus: document.getElementById('rpcControllerStatus'),
            name: document.getElementById('rpcName'),
            details: document.getElementById('rpcDetails'),
            state: document.getElementById('rpcState'),
            largeKey: document.getElementById('rpcLargeImageKey'),
            largeText: document.getElementById('rpcLargeImageText'),
            largeConfigPreview: document.getElementById('rpcLargeImagePreview'),
            smallKey: document.getElementById('rpcSmallImageKey'),
            smallText: document.getElementById('rpcSmallImageText'),
            smallConfigPreview: document.getElementById('rpcSmallImagePreview'),
            timestamp: document.getElementById('rpcTimestamp'),
            customTime: document.getElementById('rpcCustomTime'),
            toggle: document.getElementById('rpcToggle'),
            btn1Label: document.getElementById('rpcButton1Label'),
            btn1Url: document.getElementById('rpcButton1Url'),
            btn2Label: document.getElementById('rpcButton2Label'),
            btn2Url: document.getElementById('rpcButton2Url'),

            // Preview Elements
            pName: document.getElementById('previewName'),
            pDetails: document.getElementById('previewDetails'),
            pState: document.getElementById('previewState'),
            pLargeImg: document.getElementById('previewLargeImage'),
            pSmallImg: document.getElementById('previewSmallImage'),
            pTimestamp: document.getElementById('previewTimestamp'),
            pButtons: document.getElementById('previewButtons'),
            pBtn1: document.getElementById('previewBtn1'),
            pBtn2: document.getElementById('previewBtn2')
        };

        // 1. Load Config & Populate Fields
        try {
            const config = await window.pywebview.api.get_config();
            if (config.rpc) {
                if (config.rpc.name) DOM.name.value = config.rpc.name;
                if (config.rpc.details) DOM.details.value = config.rpc.details;
                if (config.rpc.state) DOM.state.value = config.rpc.state;
                if (config.rpc.large_image) DOM.largeKey.value = config.rpc.large_image;
                if (config.rpc.large_text) DOM.largeText.value = config.rpc.large_text;
                if (config.rpc.small_image) DOM.smallKey.value = config.rpc.small_image;
                if (config.rpc.small_text) DOM.smallText.value = config.rpc.small_text;
                if (config.rpc.timestamp_mode) DOM.timestamp.checked = config.rpc.timestamp_mode;
                if (config.rpc.timestamp_offset) DOM.customTime.value = config.rpc.timestamp_offset;

                if (config.rpc.button1_label) DOM.btn1Label.value = config.rpc.button1_label;
                if (config.rpc.button1_url) DOM.btn1Url.value = config.rpc.button1_url;
                if (config.rpc.button2_label) DOM.btn2Label.value = config.rpc.button2_label;
                if (config.rpc.button2_url) DOM.btn2Url.value = config.rpc.button2_url;

                // Auto-start if enabled in config
                if (config.rpc.enabled) {
                    DOM.toggle.checked = true;
                    // We need to wait for appId to be fetched, so we'll do a quick check loop or just wait for the controller info
                    // Instead of complex logic, let's simply call the start logic after a short delay to allow appId fetch
                    setTimeout(() => DOM.toggle.dispatchEvent(new Event('change')), 1000);
                }
            }
        } catch (e) {
            console.error("Error loading RPC config:", e);
        }

        // Live Preview Logic
        const updatePreview = () => {
            DOM.pName.textContent = DOM.name.value || 'My Game';
            DOM.pDetails.textContent = DOM.details.value || '';
            DOM.pState.textContent = DOM.state.value || '';

            // Large Image
            if (DOM.largeKey.value && DOM.largeKey.value.startsWith('http')) {
                DOM.pLargeImg.src = DOM.largeKey.value;
                if (DOM.largeConfigPreview) DOM.largeConfigPreview.src = DOM.largeKey.value;
            } else {
                DOM.pLargeImg.src = "https://cdn.discordapp.com/embed/avatars/0.png";
                if (DOM.largeConfigPreview) DOM.largeConfigPreview.src = "https://cdn.discordapp.com/embed/avatars/0.png";
            }
            DOM.pLargeImg.title = DOM.largeText.value;

            // Small Image
            if (DOM.smallKey.value) {
                DOM.pSmallImg.style.display = 'block';
                if (DOM.smallKey.value.startsWith('http')) {
                    DOM.pSmallImg.src = DOM.smallKey.value;
                    if (DOM.smallConfigPreview) DOM.smallConfigPreview.src = DOM.smallKey.value;
                } else {
                    DOM.pSmallImg.src = "https://cdn.discordapp.com/embed/avatars/1.png";
                }
                DOM.pSmallImg.title = DOM.smallText.value;
            } else {
                DOM.pSmallImg.style.display = 'none';
            }

            // Timestamp - Show in HH:MM:SS format
            if (DOM.timestamp.checked) {
                DOM.pTimestamp.style.display = 'block';
                const h = parseFloat(DOM.customTime.value) || 0;
                const totalSeconds = Math.floor(h * 3600);
                const hours = Math.floor(totalSeconds / 3600);
                const mins = Math.floor((totalSeconds % 3600) / 60);
                const secs = totalSeconds % 60;
                DOM.pTimestamp.textContent = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')} elapsed`;
            } else {
                DOM.pTimestamp.style.display = 'none';
            }

            // Buttons
            const hasBtn1 = DOM.btn1Label.value && DOM.btn1Url.value;
            const hasBtn2 = DOM.btn2Label.value && DOM.btn2Url.value;
            if (hasBtn1 || hasBtn2) {
                DOM.pButtons.style.display = 'flex';
                DOM.pBtn1.textContent = DOM.btn1Label.value || 'Button';
                DOM.pBtn1.style.display = hasBtn1 ? 'block' : 'none';
                DOM.pBtn2.textContent = DOM.btn2Label.value || 'Button';
                DOM.pBtn2.style.display = hasBtn2 ? 'block' : 'none';
            } else {
                DOM.pButtons.style.display = 'none';
            }
        };

        // --- Helper: Get RPC Data Payload for Discord ---
        const getRpcPayload = () => {
            let startTimestamp = Date.now();
            if (DOM.timestamp.checked) {
                const h = parseFloat(DOM.customTime.value);
                if (!isNaN(h) && h > 0) {
                    const offset = h * 3600 * 1000;
                    startTimestamp = Math.max(1, startTimestamp - offset);
                }
            }

            const buttons = [];
            if (DOM.btn1Label.value && DOM.btn1Url.value) {
                buttons.push({ label: DOM.btn1Label.value, url: DOM.btn1Url.value });
            }
            if (DOM.btn2Label.value && DOM.btn2Url.value) {
                buttons.push({ label: DOM.btn2Label.value, url: DOM.btn2Url.value });
            }

            return {
                application_id: DOM.appId.value,
                name: DOM.name.value || null,
                details: DOM.details.value || null,
                state: DOM.state.value || null,
                assets: {
                    large_image: DOM.largeKey.value || null,
                    large_text: DOM.largeText.value || null,
                    small_image: DOM.smallKey.value || null,
                    small_text: DOM.smallText.value || null
                },
                timestamps: DOM.timestamp.checked ? { start: startTimestamp } : null,
                buttons: buttons.length > 0 ? buttons : null
            };
        };

        // --- Auto-Save & Auto-Update Logic ---
        let saveTimeout;
        const autoSaveAndRefresh = () => {
            // 1. Prepare Config Object
            const configData = {
                enabled: DOM.toggle.checked,
                name: DOM.name.value,
                details: DOM.details.value,
                state: DOM.state.value,
                large_image: DOM.largeKey.value,
                large_text: DOM.largeText.value,
                small_image: DOM.smallKey.value,
                small_text: DOM.smallText.value,
                timestamp_mode: DOM.timestamp.checked,
                timestamp_offset: DOM.customTime.value,
                button1_label: DOM.btn1Label.value,
                button1_url: DOM.btn1Url.value,
                button2_label: DOM.btn2Label.value,
                button2_url: DOM.btn2Url.value
            };

            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(async () => {
                // Save to config
                if (window.pywebview?.api?.save_config) {
                    try {
                        await window.pywebview.api.save_config({ 'rpc': configData });
                        console.log("RPC Config saved.");
                    } catch (e) {
                        console.error("Failed to save RPC config:", e);
                    }
                }

                // If active, refresh presence
                if (DOM.toggle.checked && DOM.appId.value) {
                    const payload = getRpcPayload();
                    try {
                        if (window.pywebview?.api?.set_activity) {
                            await window.pywebview.api.set_activity(payload);
                            console.log("RPC Auto-updated.");
                        }
                    } catch (e) {
                        console.error("Failed to auto-update RPC:", e);
                    }
                }
            }, 1000); // 1-second debounce
        };

        // Bind inputs
        const allInputs = [DOM.name, DOM.details, DOM.state, DOM.largeKey, DOM.largeText,
        DOM.smallKey, DOM.smallText, DOM.customTime,
        DOM.btn1Label, DOM.btn1Url, DOM.btn2Label, DOM.btn2Url];

        allInputs.forEach(el => {
            if (el) {
                el.addEventListener('input', () => {
                    updatePreview();
                    autoSaveAndRefresh();
                });
            }
        });

        DOM.timestamp.addEventListener('change', () => {
            updatePreview();
            autoSaveAndRefresh();
        });

        // Fetch Controller ID
        (async () => {
            if (window.pywebview?.api?.get_controller_info) {
                DOM.controllerStatus.innerHTML = '<span class="status-dot"></span> Checking...';
                try {
                    const res = await window.pywebview.api.get_controller_info();
                    if (res.success && res.id) {
                        DOM.appId.value = res.id;
                        DOM.controllerStatus.innerHTML = '<span class="status-dot active"></span> Connected';
                    } else {
                        DOM.controllerStatus.innerHTML = '<span class="status-dot" style="background:#f04747"></span> Not found';
                    }
                } catch (e) {
                    console.error(e);
                }
            }
        })();

        // Toggle RPC (Manual Start/Stop)
        DOM.toggle.addEventListener('change', async (e) => {
            const active = e.target.checked;
            const statusText = document.getElementById('rpcStatusText');
            const errContainer = document.getElementById('rpcErrorContainer');
            errContainer.style.display = 'none';

            if (active) {
                // Update config enabled state immediately
                if (window.pywebview?.api?.save_config) {
                    window.pywebview.api.save_config({ 'rpc.enabled': true }).catch(console.error);
                }

                if (!DOM.appId.value) {
                    errContainer.textContent = "Controller ID missing.";
                    errContainer.style.display = 'block';
                    DOM.toggle.checked = false;
                    return;
                }

                statusText.textContent = "Starting...";
                const data = getRpcPayload();

                try {
                    if (window.pywebview?.api?.set_activity) {
                        const res = await window.pywebview.api.set_activity(data);
                        if (res.success) {
                            statusText.textContent = "Active";
                            statusText.className = "status-text active";
                        } else {
                            throw new Error(res.error);
                        }
                    }
                } catch (e) {
                    statusText.textContent = "Error";
                    statusText.className = "status-text error";
                    errContainer.textContent = e.message;
                    errContainer.style.display = 'block';
                    DOM.toggle.checked = false;
                }
            } else {
                // Update config enabled state
                if (window.pywebview?.api?.save_config) {
                    window.pywebview.api.save_config({ 'rpc.enabled': false }).catch(console.error);
                }

                if (window.pywebview?.api?.clear_activity) {
                    await window.pywebview.api.clear_activity();
                    statusText.textContent = "Disabled";
                    statusText.className = "status-text";
                }
            }
        });

        updatePreview();
    }
}

// --- Robust Orbyte/pywebview Initialization ---
let _orbyteDomReady = false;
let _orbytePywebviewReady = false;
let _orbyteStarted = false;

function tryStartOrbyteApp() {
    if (_orbyteStarted) return;
    if (!_orbyteDomReady || !_orbytePywebviewReady) return;
    _orbyteStarted = true;
    console.log('[Orbyte] Interface initializing...');
    window.orbyteInterface = new OrbyteInterface();
    // Always start token connection handshake after interface init
    function callTryInitialLogin(retries = 10) {
        if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.try_initial_login === 'function') {
            console.log('[Orbyte] Call to pywebview.api.try_initial_login()');
            window.orbyteInterface.start();
        } else if (retries > 0) {
            setTimeout(() => callTryInitialLogin(retries - 1), 200);
        } else {
            console.error('[Orbyte] pywebview.api.try_initial_login not available after timeout.');
            if (window.orbyteInterface && typeof window.orbyteInterface.showTokenModal === 'function') {
                window.orbyteInterface.showTokenModal('Backend connection unavailable.');
            }
        }
    }
    callTryInitialLogin();
}

document.addEventListener('DOMContentLoaded', () => {
    _orbyteDomReady = true;
    tryStartOrbyteApp();
});

if (window.pywebview) {
    window.addEventListener('pywebviewready', () => {
        _orbytePywebviewReady = true;
        tryStartOrbyteApp();
    });
} else {
    // Pour le debug hors pywebview (ex: navigateur direct)
    _orbytePywebviewReady = true;
    tryStartOrbyteApp();
}

// This function is now the single point of entry for Python callbacks
window.handlePythonEvent = (eventType, data) => {
    if (window.orbyteInterface) {
        window.orbyteInterface.handlePythonEvent(eventType, data);
    }
};