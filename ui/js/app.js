/* ==========================================================================
   IMAP Inbox Helper JavaScript Core Control
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // Shared state variables
    let currentEmails = [];
    let selectedEmailId = null;
    let onlyImportantFilter = false;
    let autoUpdateInterval = null;

    // Wait until the pywebview API is initialized on the window
    function initApp() {
        if (window.pywebview && window.pywebview.api) {
            console.log("pywebview API loaded successfully.");

            // Perform initial loads
            loadEmails();
            loadSettings();
            loadLogs();

            // Set up polling to auto-update emails and logs in real-time
            autoUpdateInterval = setInterval(() => {
                loadEmails(onlyImportantFilter, false); // silent refresh
                loadLogs(false); // silent refresh
            }, 3000);

        } else {
            // Keep polling until the window.pywebview exists
            setTimeout(initApp, 100);
        }
    }

    // Start initialization sequence
    initApp();

    // ==========================================================================
    // Sidebar Tabs Router
    // ==========================================================================
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");

            // Toggle active navigation button style
            navButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            // Toggle active content panel visibility
            tabContents.forEach(tab => {
                tab.classList.remove("active");
                if (tab.id === targetTab) {
                    tab.classList.add("active");
                }
            });

            // Perform context-specific updates upon loading a tab
            if (targetTab === "dashboard-tab") {
                loadEmails(onlyImportantFilter);
            } else if (targetTab === "digest-tab") {
                loadDigest();
            } else if (targetTab === "rules-tab") {
                loadSettings();
            } else if (targetTab === "logs-tab") {
                loadLogs();
            }
        });
    });

    // ==========================================================================
    // Dashboard Logic (Tab 1)
    // ==========================================================================
    const emailFeedList = document.getElementById("email-feed-list");
    const emailDetailPane = document.getElementById("email-detail-pane");
    const filterAllBtn = document.getElementById("filter-all-btn");
    const filterImportantBtn = document.getElementById("filter-important-btn");

    const countImportantEl = document.getElementById("important-count");
    const countClutterEl = document.getElementById("clutter-count");
    const countTotalEl = document.getElementById("total-count");

    // Filter Buttons listeners
    filterAllBtn.addEventListener("click", () => {
        filterAllBtn.classList.add("active");
        filterImportantBtn.classList.remove("active");
        onlyImportantFilter = false;
        loadEmails(false);
    });

    filterImportantBtn.addEventListener("click", () => {
        filterImportantBtn.classList.add("active");
        filterAllBtn.classList.remove("active");
        onlyImportantFilter = true;
        loadEmails(true);
    });

    // Fetch Emails from SQLite DB via Python bridge
    function loadEmails(onlyImportant = false, renderLoading = true) {
        if (!window.pywebview || !window.pywebview.api) return;

        if (renderLoading && emailFeedList.children.length <= 1) {
            emailFeedList.innerHTML = `<div class="empty-state"><p>Synchronizing local email history...</p></div>`;
        }

        window.pywebview.api.get_emails(onlyImportant).then(response => {
            const res = JSON.parse(response);
            if (res.success) {
                currentEmails = res.data;
                renderEmailList(currentEmails);
                updateDashboardCounters(currentEmails);
            } else {
                console.error("Failed to load emails:", res.error);
            }
        });
    }

    // Render list elements dynamically
    function renderEmailList(emails) {
        if (emails.length === 0) {
            emailFeedList.innerHTML = `
                <div class="empty-state">
                    <p>No emails found. Click <strong>Sync Now</strong> to check your IMAP server.</p>
                </div>`;
            return;
        }

        // Save current scroll position
        const scrollTop = emailFeedList.scrollTop;
        emailFeedList.innerHTML = "";

        emails.forEach(email => {
            const isSelected = selectedEmailId === email.message_id;
            const isUnread = !email.is_read;

            const card = document.createElement("div");
            card.className = `email-card ${isSelected ? 'selected' : ''} ${isUnread ? 'unread' : ''}`;
            card.setAttribute("data-id", email.message_id);

            const scoreClass = email.is_important ? "score-high" : "score-low";
            const scoreTag = email.is_important ? "Important" : "Bulk";
            const scoreStr = `${email.importance_score} | ${scoreTag}`;

            // Format sender display name cleanly
            let senderDisplay = email.sender.replace(/<.*>/, "").trim();
            if (!senderDisplay) {
                senderDisplay = email.sender;
            }

            // Extract date time
            let dateStr = "";
            try {
                const date = new Date(email.date_sent);
                dateStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " " + date.toLocaleDateString([], { month: 'short', day: 'numeric' });
                if (dateStr.includes("Invalid")) dateStr = email.date_sent;
            } catch (e) {
                dateStr = email.date_sent;
            }

            card.innerHTML = `
                <div class="email-card-header">
                    <span class="email-sender">${senderDisplay}</span>
                    <span class="email-score-tag ${scoreClass}">${scoreStr}</span>
                </div>
                <div class="email-subject">
                    ${email.subject || "(No Subject)"}
                </div>
                <div class="email-snippet">
                    ${email.body_snippet || "(Empty content snippet)"}
                </div>
                <div class="email-card-footer">
                    <span>${dateStr}</span>
                    ${isUnread ? '<span class="unread-dot"></span>' : ''}
                </div>
            `;

            card.addEventListener("click", () => {
                selectEmailCard(email);
            });

            emailFeedList.appendChild(card);
        });

        // Restore scroll position
        emailFeedList.scrollTop = scrollTop;
    }

    function selectEmailCard(email) {
        selectedEmailId = email.message_id;

        // Highlight active card
        document.querySelectorAll(".email-card").forEach(c => c.classList.remove("selected"));
        const card = document.querySelector(`.email-card[data-id="${email.message_id}"]`);
        if (card) card.classList.add("selected");

        renderEmailDetail(email);
    }

    function renderEmailDetail(email) {
        const scoreClass = email.is_important ? "score-high" : "score-low";
        const scoreBadge = email.is_important ? "IMPORTANT" : "BULK / CLUTTER";

        // Split reasons
        const reasons = email.classification_reason ? email.classification_reason.split("; ") : [];
        const reasonsListHtml = reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("");

        emailDetailPane.innerHTML = `
            <div class="detail-view">
                <div class="detail-header">
                    <div class="detail-meta">
                        <div class="detail-meta-row">
                            <span class="meta-label">From:</span>
                            <span class="meta-value">${escapeHtml(email.sender)}</span>
                        </div>
                        <div class="detail-meta-row">
                            <span class="meta-label">Date:</span>
                            <span class="meta-value">${email.date_sent}</span>
                        </div>
                    </div>
                    <h3 class="detail-subject">${escapeHtml(email.subject || "(No Subject)")}</h3>
                </div>

                <div class="classification-report">
                    <div class="report-header">
                        <span class="report-title">Router Rating Report</span>
                        <div class="report-score">
                            <span>Score:</span>
                            <span class="score-num ${scoreClass}">${email.importance_score} / 100 [${scoreBadge}]</span>
                        </div>
                    </div>
                    <ul class="report-reasons">
                        ${reasonsListHtml || "<li>No specific priority criteria met. Classified under standard priority.</li>"}
                    </ul>
                </div>

                <div class="detail-body-container">${escapeHtml(email.body_snippet || "Content is empty.")}</div>

                <div class="detail-actions">
                    <button class="btn btn-secondary" id="action-read-btn">Mark as Read</button>
                    <button class="btn btn-secondary" id="action-archive-btn">Move to Archive</button>
                    <button class="btn btn-danger" id="action-delete-btn">Delete Mail</button>
                </div>
            </div>
        `;

        // Action Button click handlers
        document.getElementById("action-read-btn").addEventListener("click", () => triggerEmailAction(email.message_id, "mark_read"));
        document.getElementById("action-archive-btn").addEventListener("click", () => triggerEmailAction(email.message_id, "archive"));
        document.getElementById("action-delete-btn").addEventListener("click", () => triggerEmailAction(email.message_id, "delete"));
    }

    function triggerEmailAction(messageId, action) {
        if (!window.pywebview || !window.pywebview.api) return;

        const buttonMap = {
            "mark_read": document.getElementById("action-read-btn"),
            "archive": document.getElementById("action-archive-btn"),
            "delete": document.getElementById("action-delete-btn")
        };

        const activeBtn = buttonMap[action];
        const originalText = activeBtn.innerText;
        activeBtn.innerText = "Processing...";
        activeBtn.disabled = true;

        window.pywebview.api.perform_action(messageId, action).then(response => {
            const res = JSON.parse(response);
            if (res.success) {
                selectedEmailId = null;
                emailDetailPane.innerHTML = `
                    <div class="empty-state">
                        <p>Mail processed successfully. Selecting another email...</p>
                    </div>`;
                loadEmails(onlyImportantFilter);
                loadLogs();
            } else {
                activeBtn.innerText = originalText;
                activeBtn.disabled = false;
                alert("Action failed: " + res.error);
            }
        });
    }

    function updateDashboardCounters(emails) {
        // Calculate totals based on currently loaded SQLite data
        if (!emails) return;

        let importantCount = 0;
        let clutterCount = 0;

        emails.forEach(e => {
            if (e.is_important) importantCount++;
            else clutterCount++;
        });

        countImportantEl.innerText = importantCount;
        countClutterEl.innerText = clutterCount;
        countTotalEl.innerText = emails.length;
    }

    // Manual Sync trigger button
    const manualSyncBtn = document.getElementById("manual-sync-btn");
    manualSyncBtn.addEventListener("click", () => {
        if (!window.pywebview || !window.pywebview.api) return;

        manualSyncBtn.innerText = "Syncing...";
        manualSyncBtn.disabled = true;

        window.pywebview.api.trigger_manual_sync().then(response => {
            const res = JSON.parse(response);
            setTimeout(() => {
                manualSyncBtn.innerText = "Sync Now";
                manualSyncBtn.disabled = false;
                loadEmails(onlyImportantFilter);
                loadLogs();
            }, 1500);
        });
    });

    // ==========================================================================
    // Configuration Settings Logic (Tab 2)
    // ==========================================================================
    const settingsForm = document.getElementById("settings-form");
    const resetSettingsBtn = document.getElementById("reset-settings-btn");
    const saveSettingsBtn = document.getElementById("save-settings-btn");

    const oauthStatusBadge = document.getElementById("oauth-status-badge");
    const oauthConnectBtn = document.getElementById("oauth-connect-btn");
    const oauthStatusText = document.getElementById("oauth-status-text");

    let oauthCheckInterval = null;

    let firstLaunchCheckDone = false;

    function loadSettings() {
        if (!window.pywebview || !window.pywebview.api) return;

        window.pywebview.api.get_settings().then(response => {
            const res = JSON.parse(response);
            if (res.success) {
                const data = res.data;
                // Populate form inputs
                document.getElementById("IMAP_HOST").value = data.IMAP_HOST || "";
                document.getElementById("IMAP_PORT").value = data.IMAP_PORT || 993;
                document.getElementById("IMAP_SSL").checked = data.IMAP_SSL;
                document.getElementById("IMAP_USER").value = data.IMAP_USER || "";
                document.getElementById("IMAP_PASSWORD").value = data.IMAP_PASSWORD || "";
                document.getElementById("MONITOR_FOLDER").value = data.MONITOR_FOLDER || "INBOX";
                document.getElementById("POLL_INTERVAL").value = data.POLL_INTERVAL || 300;

                // Google OAuth details
                document.getElementById("google_client_id").value = data.google_client_id || "";
                document.getElementById("google_client_secret").value = data.google_client_secret || "";

                // Slider
                const slider = document.getElementById("IMPORTANCE_THRESHOLD");
                slider.value = data.IMPORTANCE_THRESHOLD || 50;
                slider.nextElementSibling.innerText = slider.value;

                // Textareas
                document.getElementById("WHITELIST_SENDERS").value = data.WHITELIST_SENDERS || "";
                document.getElementById("BLACKLIST_SENDERS").value = data.BLACKLIST_SENDERS || "";

                // Synchronize OAuth Status
                loadOAuthStatus();

                // Onboarding Check: Toggle Lock Screen Login Wall if unconfigured
                const hasAppPassword = data.IMAP_USER && data.IMAP_PASSWORD;
                const hasOAuth = data.oauth_enabled;
                const loginWall = document.getElementById("login-wall-overlay");

                if (!hasAppPassword && !hasOAuth) {
                    if (loginWall) loginWall.classList.remove("hidden");
                } else {
                    if (loginWall) loginWall.classList.add("hidden");
                }
            }
        });
    }

    function loadOAuthStatus() {
        if (!window.pywebview || !window.pywebview.api) return;

        window.pywebview.api.get_oauth_status().then(response => {
            const res = JSON.parse(response);
            if (res.success) {
                const data = res.data;
                if (data.authorized && data.enabled) {
                    oauthStatusBadge.className = "badge score-high";
                    oauthStatusBadge.innerText = "Authorized";
                    oauthConnectBtn.innerText = "Disconnect Gmail";
                    oauthStatusText.innerHTML = `Connected securely to Gmail as: <strong>${escapeHtml(data.email)}</strong>`;
                } else {
                    oauthStatusBadge.className = "badge score-low";
                    oauthStatusBadge.innerText = "Deactivated";
                    oauthConnectBtn.innerText = "Connect Gmail";
                    oauthStatusText.innerText = "Using App Password by default. Save Google credentials above to connect.";
                }
            }
        });
    }

    // Google OAuth Link Button click handler
    oauthConnectBtn.addEventListener("click", () => {
        if (!window.pywebview || !window.pywebview.api) return;

        window.pywebview.api.get_oauth_status().then(response => {
            const res = JSON.parse(response);
            if (res.success) {
                const data = res.data;

                if (data.authorized && data.enabled) {
                    // Disconnect
                    if (confirm("Disconnect Google Sign-In and revert to standard App Password logins?")) {
                        window.pywebview.api.disconnect_oauth().then(discRes => {
                            const disc = JSON.parse(discRes);
                            if (disc.success) {
                                loadOAuthStatus();
                                loadLogs();
                            }
                        });
                    }
                } else {
                    // Start Google auth flow
                    // Validate that ID and Secret are configured
                    const clientID = document.getElementById("google_client_id").value.trim();
                    const clientSecret = document.getElementById("google_client_secret").value.trim();

                    if (!clientID || !clientSecret) {
                        alert("Please enter both Google Client ID and Client Secret, click 'Save Configurations', and then click 'Connect Gmail'.");
                        return;
                    }

                    oauthConnectBtn.innerText = "Connecting...";
                    oauthConnectBtn.disabled = true;

                    window.pywebview.api.start_oauth_flow().then(flowRes => {
                        const flow = JSON.parse(flowRes);
                        if (flow.success) {
                            alert("Opening Google Login screen in your browser. Please log in and authorize the application, then return here.");

                            // Poll in background for auth state change
                            let pollCounter = 0;
                            if (oauthCheckInterval) clearInterval(oauthCheckInterval);

                            oauthCheckInterval = setInterval(() => {
                                pollCounter++;
                                window.pywebview.api.get_oauth_status().then(statusRes => {
                                    const statusObj = JSON.parse(statusRes);
                                    if (statusObj.success && statusObj.data.authorized && statusObj.data.enabled) {
                                        clearInterval(oauthCheckInterval);
                                        loadOAuthStatus();
                                        loadLogs();
                                        alert("Gmail OAuth Direct Sync linked successfully!");
                                    }
                                });

                                // Timeout after 60 seconds of polling
                                if (pollCounter >= 40) {
                                    clearInterval(oauthCheckInterval);
                                    loadOAuthStatus();
                                    alert("Google Authorization timed out. Please try again.");
                                }
                            }, 1500);

                        } else {
                            oauthConnectBtn.innerText = "Connect Gmail";
                            oauthConnectBtn.disabled = false;
                            alert("Authorization failed: " + flow.error);
                        }
                    });
                }
            }
        });
    });

    settingsForm.addEventListener("submit", () => {
        if (!window.pywebview || !window.pywebview.api) return;

        saveSettingsBtn.innerText = "Saving...";
        saveSettingsBtn.disabled = true;

        const config = {
            IMAP_HOST: document.getElementById("IMAP_HOST").value,
            IMAP_PORT: parseInt(document.getElementById("IMAP_PORT").value),
            IMAP_SSL: document.getElementById("IMAP_SSL").checked,
            IMAP_USER: document.getElementById("IMAP_USER").value,
            IMAP_PASSWORD: document.getElementById("IMAP_PASSWORD").value,
            MONITOR_FOLDER: document.getElementById("MONITOR_FOLDER").value,
            POLL_INTERVAL: parseInt(document.getElementById("POLL_INTERVAL").value),
            IMPORTANCE_THRESHOLD: parseInt(document.getElementById("IMPORTANCE_THRESHOLD").value),
            WHITELIST_SENDERS: document.getElementById("WHITELIST_SENDERS").value,
            BLACKLIST_SENDERS: document.getElementById("BLACKLIST_SENDERS").value,
            // Include Google details in payload
            google_client_id: document.getElementById("google_client_id").value,
            google_client_secret: document.getElementById("google_client_secret").value
        };

        window.pywebview.api.save_settings(JSON.stringify(config)).then(response => {
            const res = JSON.parse(response);
            saveSettingsBtn.innerText = "Save Configurations";
            saveSettingsBtn.disabled = false;

            if (res.success) {
                alert("Configurations saved and reloaded successfully!");
                loadSettings();
                loadLogs();
            } else {
                alert("Failed to save settings: " + res.error);
            }
        });
    });

    resetSettingsBtn.addEventListener("click", () => {
        if (confirm("Reset inputs to saved configuration values?")) {
            loadSettings();
        }
    });

    // ==========================================================================
    // Classifier Sandbox Logic (Tab 3)
    // ==========================================================================
    const runSandboxBtn = document.getElementById("run-sandbox-btn");
    const sandboxResultPane = document.getElementById("sandbox-result-pane");

    runSandboxBtn.addEventListener("click", () => {
        if (!window.pywebview || !window.pywebview.api) return;

        const sender = document.getElementById("sb-sender").value.trim();
        const subject = document.getElementById("sb-subject").value.trim();
        const body = document.getElementById("sb-body").value.trim();
        const headersRaw = document.getElementById("sb-headers").value.trim();

        if (!sender || !body) {
            alert("Sender Address and Email Body plain text are required to test!");
            return;
        }

        // Validate raw headers JSON
        let headers = {};
        if (headersRaw) {
            try {
                headers = JSON.parse(headersRaw);
            } catch (e) {
                alert("Invalid Custom Headers JSON. Please enter valid JSON or clear the field.");
                return;
            }
        }

        // Inject standard headers
        headers["from"] = sender;
        headers["subject"] = subject;

        runSandboxBtn.innerText = "Analyzing simulated parameters...";
        runSandboxBtn.disabled = true;

        window.pywebview.api.test_classifier(JSON.stringify(headers), body).then(response => {
            runSandboxBtn.innerText = "Run Sandbox Evaluation";
            runSandboxBtn.disabled = false;

            const res = JSON.parse(response);
            if (res.success) {
                renderSandboxResult(res.data);
            } else {
                alert("Evaluation failed: " + res.error);
            }
        });
    });

    function renderSandboxResult(result) {
        const ratingClass = result.is_important ? "score-high" : "score-low";
        const ratingTag = result.is_important ? "IMPORTANT" : "BULK / CLUTTER";

        // Parse matches
        const reasons = result.classification_reason ? result.classification_reason.split("; ") : [];

        let reasonsHtml = reasons.map(r => {
            // Add custom visual weight markers
            let pointSpan = "";
            if (r.includes("(+")) {
                const pts = r.match(/\(\+(\d+)\)/);
                if (pts) pointSpan = `<span class="reason-pts-pos">+${pts[1]} Pts</span>`;
            } else if (r.includes("(-")) {
                const pts = r.match(/\(-(\d+)\)/);
                if (pts) pointSpan = `<span class="reason-pts-neg">-${pts[1]} Pts</span>`;
            }

            return `
                <div class="sandbox-reason-item">
                    <span>${escapeHtml(r)}</span>
                    ${pointSpan}
                </div>`;
        }).join("");

        sandboxResultPane.innerHTML = `
            <div>
                <div class="sandbox-report-header">
                    <span class="sandbox-report-title">Simulated Evaluation Output</span>
                    <div class="sandbox-badge-row">
                        <span class="sandbox-badge ${ratingClass}">${ratingTag}</span>
                        <span class="sandbox-score">${result.score} / 100</span>
                    </div>
                </div>

                <div class="sandbox-report-body">
                    <h4>Matched Rules Breakdown</h4>
                    <div class="sandbox-reasons-list">
                        ${reasonsHtml || '<div class="sandbox-reason-item">No specific classification filters matched. Rated neutral 50.</div>'}
                    </div>
                </div>
            </div>
        `;
    }

    // ==========================================================================
    // System Console Logs Logic (Tab 4)
    // ==========================================================================
    const consoleLogsList = document.getElementById("console-logs-list");
    const refreshLogsBtn = document.getElementById("refresh-logs-btn");
    const clearDbBtn = document.getElementById("clear-db-btn");

    refreshLogsBtn.addEventListener("click", () => {
        loadLogs();
    });

    clearDbBtn.addEventListener("click", () => {
        if (confirm("WARNING: This will delete all indexed emails and system log history from SQLite permanently! Are you absolutely sure?")) {
            if (!window.pywebview || !window.pywebview.api) return;

            window.pywebview.api.clear_database().then(response => {
                const res = JSON.parse(response);
                if (res.success) {
                    alert("Database tables wiped successfully.");
                    selectedEmailId = null;
                    emailDetailPane.innerHTML = `<div class="empty-state"><p>Select an email from the left feed.</p></div>`;
                    loadEmails(onlyImportantFilter);
                    loadLogs();
                }
            });
        }
    });

    function loadLogs(renderLoading = true) {
        if (!window.pywebview || !window.pywebview.api) return;

        if (renderLoading && consoleLogsList.children.length === 0) {
            consoleLogsList.innerHTML = `<div style="color: var(--text-muted);">Fetching syslog feed...</div>`;
        }

        window.pywebview.api.get_logs().then(response => {
            const res = JSON.parse(response);
            if (res.success) {
                renderLogs(res.data);
            }
        });
    }

    function renderLogs(logs) {
        if (logs.length === 0) {
            consoleLogsList.innerHTML = `<div style="color: var(--text-muted);">Console log is currently empty.</div>`;
            return;
        }

        const scrollTop = consoleLogsList.scrollTop;
        consoleLogsList.innerHTML = "";

        logs.forEach(log => {
            // Format ISO datetime to hh:mm:ss
            let timeStr = "";
            try {
                const d = new Date(log.timestamp);
                timeStr = d.toLocaleTimeString([], { hour12: false });
            } catch (e) {
                timeStr = log.timestamp;
            }

            const row = document.createElement("div");
            row.className = "log-row";

            const tagClass = `tag-${log.level.toLowerCase()}`;
            const levelTag = `[${log.level.toUpperCase()}]`;

            row.innerHTML = `
                <span class="log-time">${timeStr}</span>
                <span class="log-tag ${tagClass}">${levelTag}</span>
                <span class="log-msg">${escapeHtml(log.message)}</span>
            `;

            consoleLogsList.appendChild(row);
        });

        // Restore scroll position
        consoleLogsList.scrollTop = scrollTop;
    }

    // =========================================================================
    // Login Wall Overlay Controls
    // =========================================================================
    const loginTabGoogleBtn = document.getElementById("login-tab-google-btn");
    const loginTabPasswdBtn = document.getElementById("login-tab-passwd-btn");
    const loginModeGoogle = document.getElementById("login-mode-google");
    const loginModePasswd = document.getElementById("login-mode-passwd");

    const wallOauthConnectBtn = document.getElementById("wall-oauth-connect-btn");
    const wallPasswdConnectBtn = document.getElementById("wall-passwd-connect-btn");
    const viewGuideLink = document.getElementById("view-guide-link");

    // Toggle Custom OAuth Keys
    const useCustomOauthCheckbox = document.getElementById("wall-oauth-use-custom");
    const customOauthFields = document.getElementById("wall-oauth-custom-fields");
    if (useCustomOauthCheckbox && customOauthFields) {
        useCustomOauthCheckbox.addEventListener("change", () => {
            if (useCustomOauthCheckbox.checked) {
                customOauthFields.classList.remove("hidden");
            } else {
                customOauthFields.classList.add("hidden");
            }
        });
    }

    // Toggle Advanced IMAP Settings
    const useAdvancedImapCheckbox = document.getElementById("wall-passwd-use-advanced");
    const advancedImapFields = document.getElementById("wall-passwd-advanced-fields");
    if (useAdvancedImapCheckbox && advancedImapFields) {
        useAdvancedImapCheckbox.addEventListener("change", () => {
            if (useAdvancedImapCheckbox.checked) {
                advancedImapFields.classList.remove("hidden");
            } else {
                advancedImapFields.classList.add("hidden");
            }
        });
    }

    // Handle IMAP Provider Presets
    const providerDropdown = document.getElementById("wall-passwd-provider");
    const providerGuide = document.getElementById("wall-provider-instructions");
    const passwdHostInput = document.getElementById("wall-passwd-host");
    const passwdPortInput = document.getElementById("wall-passwd-port");
    const passwdSslInput = document.getElementById("wall-passwd-ssl");

    const providerSettings = {
        gmail: {
            host: "imap.gmail.com",
            port: 993,
            ssl: true,
            guide: 'Gmail App Passwords:<br>1. Go to <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color: #63b3ed; text-decoration: underline;">Google App Passwords</a>.<br>2. Generate a 16-character code (e.g. "InboxHelper").<br>3. Copy the code and paste it below.'
        },
        outlook: {
            host: "outlook.office365.com",
            port: 993,
            ssl: true,
            guide: 'Outlook App Passwords:<br>1. Go to <a href="https://account.live.com/proofs/manage/additional" target="_blank" style="color: #63b3ed; text-decoration: underline;">Microsoft Security Manage</a>.<br>2. Click "Create a new app password".<br>3. Copy the code and paste it below.'
        },
        yahoo: {
            host: "imap.mail.yahoo.com",
            port: 993,
            ssl: true,
            guide: 'Yahoo App Passwords:<br>1. Go to Yahoo Account Security > Manage App Passwords.<br>2. Generate a code and paste it below.'
        },
        icloud: {
            host: "imap.mail.me.com",
            port: 993,
            ssl: true,
            guide: 'iCloud App Passwords:<br>1. Go to <a href="https://appleid.apple.com" target="_blank" style="color: #63b3ed; text-decoration: underline;">Apple ID Manager</a>.<br>2. Under Sign-In and Security > App-Specific Passwords, generate a code.<br>3. Paste the code below.'
        },
        custom: {
            host: "",
            port: 993,
            ssl: true,
            guide: 'Enter your custom IMAP credentials below. Check the "Show Advanced IMAP Settings" box if you need to override the IMAP Host or Port.'
        }
    };

    function updateProviderPreset() {
        const val = providerDropdown.value;
        const preset = providerSettings[val];
        if (preset) {
            passwdHostInput.value = preset.host;
            passwdPortInput.value = preset.port;
            passwdSslInput.checked = preset.ssl;
            providerGuide.innerHTML = preset.guide;
        }
    }

    if (providerDropdown) {
        providerDropdown.addEventListener("change", updateProviderPreset);
        // Trigger initial preset loading
        updateProviderPreset();
    }

    // Login Card Tab switches
    if (loginTabGoogleBtn && loginTabPasswdBtn) {
        loginTabGoogleBtn.addEventListener("click", () => {
            loginTabGoogleBtn.classList.add("active");
            loginTabPasswdBtn.classList.remove("active");
            loginModeGoogle.classList.add("active");
            loginModePasswd.classList.remove("active");
        });

        loginTabPasswdBtn.addEventListener("click", () => {
            loginTabPasswdBtn.classList.add("active");
            loginTabGoogleBtn.classList.remove("active");
            loginModePasswd.classList.add("active");
            loginModeGoogle.classList.remove("active");
        });
    }

    // Google Sign-In on Login Wall
    if (wallOauthConnectBtn) {
        wallOauthConnectBtn.addEventListener("click", () => {
            if (!window.pywebview || !window.pywebview.api) return;

            const oauthEmail = document.getElementById("wall-imap-user").value.trim();
            const useCustom = document.getElementById("wall-oauth-use-custom").checked;

            let clientID = "";
            let clientSecret = "";

            if (useCustom) {
                clientID = document.getElementById("wall-client-id").value.trim();
                clientSecret = document.getElementById("wall-client-secret").value.trim();

                if (!clientID || !clientSecret) {
                    alert("Please enter both your custom Google Client ID and Client Secret.");
                    return;
                }
            }

            if (!oauthEmail) {
                alert("Please enter your Gmail address to sign in.");
                return;
            }

            wallOauthConnectBtn.innerText = "Signing In...";
            wallOauthConnectBtn.disabled = true;

            // 1. Save settings to SQLite first so OAuth knows which user to use
            const config = {
                IMAP_HOST: "imap.gmail.com",
                IMAP_PORT: 993,
                IMAP_SSL: true,
                IMAP_USER: oauthEmail,
                IMAP_PASSWORD: "",  // Not using App Password
                MONITOR_FOLDER: "INBOX",
                POLL_INTERVAL: 300,
                IMPORTANCE_THRESHOLD: 50,
                WHITELIST_SENDERS: "",
                BLACKLIST_SENDERS: "glassdoor,indeed,aliexpress,newsletter,noreply@,no-reply@",
                google_client_id: clientID,
                google_client_secret: clientSecret
            };

            window.pywebview.api.save_settings(JSON.stringify(config)).then(saveRes => {
                const saveObj = JSON.parse(saveRes);
                if (saveObj.success) {
                    // 2. Start OAuth flow passing custom keys if specified
                    window.pywebview.api.start_oauth_flow(oauthEmail, clientID, clientSecret).then(flowRes => {
                        const flow = JSON.parse(flowRes);
                        if (flow.success) {
                            alert("Opening Google Login screen in your browser. Please authorize access, then return here.");

                            let pollCounter = 0;
                            let wallInterval = setInterval(() => {
                                pollCounter++;
                                window.pywebview.api.get_oauth_status().then(statusRes => {
                                    const statusObj = JSON.parse(statusRes);
                                    if (statusObj.success && statusObj.data.authorized && statusObj.data.enabled) {
                                        clearInterval(wallInterval);
                                        wallOauthConnectBtn.innerText = "Sign In with Google";
                                        wallOauthConnectBtn.disabled = false;

                                        // Hide Overlay & Refresh
                                        document.getElementById("login-wall-overlay").classList.add("hidden");
                                        loadSettings();
                                        loadEmails();
                                        loadLogs();
                                        alert("Successfully authorized and signed in with Google!");
                                    }
                                });

                                if (pollCounter >= 40) {
                                    clearInterval(wallInterval);
                                    wallOauthConnectBtn.innerText = "Sign In with Google";
                                    wallOauthConnectBtn.disabled = false;
                                    alert("Google sign-in timed out. Please try again.");
                                }
                            }, 1500);
                        } else {
                            wallOauthConnectBtn.innerText = "Sign In with Google";
                            wallOauthConnectBtn.disabled = false;
                            alert("Authorization failed: " + flow.error);
                        }
                    });
                } else {
                    wallOauthConnectBtn.innerText = "Sign In with Google";
                    wallOauthConnectBtn.disabled = false;
                    alert("Failed to save credentials: " + saveObj.error);
                }
            });
        });
    }

    // App Password Sign-In on Login Wall
    if (wallPasswdConnectBtn) {
        wallPasswdConnectBtn.addEventListener("click", () => {
            if (!window.pywebview || !window.pywebview.api) return;

            const host = document.getElementById("wall-passwd-host").value.trim();
            const port = parseInt(document.getElementById("wall-passwd-port").value) || 993;
            const ssl = document.getElementById("wall-passwd-ssl").checked;
            const email = document.getElementById("wall-passwd-user").value.trim();
            const password = document.getElementById("wall-passwd-code").value.trim();

            if (!email || !password || !host) {
                alert("Please fill in the Host, Email, and App Password fields.");
                return;
            }

            wallPasswdConnectBtn.innerText = "Connecting...";
            wallPasswdConnectBtn.disabled = true;

            const config = {
                IMAP_HOST: host,
                IMAP_PORT: port,
                IMAP_SSL: ssl,
                IMAP_USER: email,
                IMAP_PASSWORD: password,
                MONITOR_FOLDER: "INBOX",
                POLL_INTERVAL: 300,
                IMPORTANCE_THRESHOLD: 50,
                WHITELIST_SENDERS: "",
                BLACKLIST_SENDERS: "glassdoor,indeed,aliexpress,newsletter,noreply@,no-reply@",
                google_client_id: "",
                google_client_secret: ""
            };

            window.pywebview.api.save_settings(JSON.stringify(config)).then(saveRes => {
                const saveObj = JSON.parse(saveRes);
                if (saveObj.success) {
                    // Trigger manual sync
                    window.pywebview.api.trigger_manual_sync().then(() => {
                        wallPasswdConnectBtn.innerText = "Connect & Sign In";
                        wallPasswdConnectBtn.disabled = false;

                        // Hide login wall and reload
                        document.getElementById("login-wall-overlay").classList.add("hidden");
                        loadSettings();
                        loadEmails();
                        loadLogs();
                        alert("IMAP Connection established and signed in successfully!");
                    });
                } else {
                    wallPasswdConnectBtn.innerText = "Connect & Sign In";
                    wallPasswdConnectBtn.disabled = false;
                    alert("Failed to save IMAP credentials: " + saveObj.error);
                }
            });
        });
    }

    // Onboarding setup guide instructions link
    if (viewGuideLink) {
        viewGuideLink.addEventListener("click", (e) => {
            e.preventDefault();
            alert("Google Cloud OAuth Setup Guide:\n" +
                "1. Create a free project on console.cloud.google.com\n" +
                "2. Go to APIs & Services > Credentials\n" +
                "3. Configure Consent Screen: set to External and add your email to Test Users\n" +
                "4. Create OAuth Web Application Credentials redirecting to http://localhost:8080/\n" +
                "5. Copy Client ID and Secret, paste them into the Google fields, and Sign In!");
        });
    }

    // ==========================================================================
    // Daily TL;DR Inbox Briefing & Digest Engine Tab
    // ==========================================================================
    function loadDigest() {
        if (!window.pywebview || !window.pywebview.api) return;

        window.pywebview.api.get_latest_digest().then(res => {
            const resObj = JSON.parse(res);
            if (resObj.success && resObj.data) {
                renderDigest(resObj.data);
            } else {
                renderEmptyDigest();
            }
        });
    }

    function renderDigest(digest) {
        const summariesContainer = document.getElementById("digest-summaries-list");
        const actionsContainer = document.getElementById("digest-actions-list");
        
        const summaries = JSON.parse(digest.summary_content || "[]");
        const actions = JSON.parse(digest.action_items || "[]");
        const dateStr = digest.digest_date;

        // Formats YYYY-MM-DD to beautiful readable date
        const formattedDate = new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });

        const tabHeader = document.querySelector("#digest-tab h2");
        if (tabHeader) {
            tabHeader.innerText = `Daily Briefing: ${formattedDate}`;
        }

        // Render Summaries
        if (summaries.length === 0) {
            summariesContainer.innerHTML = `
                <div class="empty-state">
                    <p>No high-priority emails were synchronized for this date.</p>
                </div>`;
        } else {
            summariesContainer.innerHTML = summaries.map(sum => `
                <div class="email-card" style="cursor: default; padding: 14px; background-color: rgba(255, 255, 255, 0.015); border: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 6px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                        <span style="font-size: 11px; font-weight: 700; color: var(--text-primary);">${escapeHtml(sum.sender)}</span>
                    </div>
                    <div style="font-size: 12px; font-weight: 600; color: var(--text-secondary); padding-bottom: 6px; border-bottom: 1px dashed rgba(255,255,255,0.03); margin-bottom: 2px;">
                        Subject: ${escapeHtml(sum.subject)}
                    </div>
                    <p style="font-size: 11px; color: var(--text-prose); line-height: 1.5; margin-bottom: 0; text-align: left;">
                        ${escapeHtml(sum.summary)}
                    </p>
                </div>
            `).join("");
        }

        // Render Actions
        if (actions.length === 0) {
            actionsContainer.innerHTML = `
                <div class="empty-state">
                    <p>No actionable items were detected in your important emails.</p>
                </div>`;
        } else {
            actionsContainer.innerHTML = actions.map((act, index) => `
                <div style="display: flex; align-items: flex-start; gap: 10px; padding: 10px; background: rgba(255,255,255,0.01); border: 1px solid var(--border-color); border-radius: var(--radius-sm); transition: var(--transition-fast);">
                    <input type="checkbox" class="digest-task-checkbox" data-date="${dateStr}" data-task="${escapeHtml(act.task)}" ${act.completed ? "checked" : ""} style="width: 14px; height: 14px; accent-color: var(--accent-indigo); cursor: pointer; margin-top: 2px;">
                    <div style="display: flex; flex-direction: column; gap: 3px;">
                        <span style="font-size: 11px; font-weight: 500; color: ${act.completed ? "var(--text-muted)" : "var(--text-primary)"}; text-decoration: ${act.completed ? "line-through" : "none"}; line-height: 1.4; text-align: left;">
                            ${escapeHtml(act.task)}
                        </span>
                        <small style="font-size: 9px; color: var(--text-muted); text-align: left;">
                            Context: ${escapeHtml(act.context_subject)}
                        </small>
                    </div>
                </div>
            `).join("");

            // Add Checkbox Toggle Listeners
            const checkboxes = actionsContainer.querySelectorAll(".digest-task-checkbox");
            checkboxes.forEach(cb => {
                cb.addEventListener("change", () => {
                    const taskDate = cb.getAttribute("data-date");
                    const taskText = cb.getAttribute("data-task");
                    const isCompleted = cb.checked;
                    
                    window.pywebview.api.toggle_digest_task(taskDate, taskText, isCompleted).then(res => {
                        const toggleRes = JSON.parse(res);
                        if (toggleRes.success) {
                            // Reload the digest to update visual styles (line-through) smoothly
                            loadDigest();
                        } else {
                            alert("Failed to update task state: " + toggleRes.error);
                        }
                    });
                });
            });
        }
    }

    function renderEmptyDigest() {
        document.getElementById("digest-summaries-list").innerHTML = `
            <div class="empty-state">
                <p>No summaries generated for today yet. Click <strong>Compile Daily Brief</strong> to run the local NLP summarizer.</p>
            </div>`;
        document.getElementById("digest-actions-list").innerHTML = `
            <div class="empty-state">
                <p>Your pending task queue is empty. Tasks will be extracted from your important emails when you compile your brief.</p>
            </div>`;
    }

    const generateDigestBtn = document.getElementById("generate-digest-btn");
    if (generateDigestBtn) {
        generateDigestBtn.addEventListener("click", () => {
            if (!window.pywebview || !window.pywebview.api) return;

            generateDigestBtn.innerText = "Compiling Summaries...";
            generateDigestBtn.disabled = true;

            window.pywebview.api.generate_fresh_digest().then(res => {
                const resObj = JSON.parse(res);
                generateDigestBtn.innerText = "Compile Daily Brief";
                generateDigestBtn.disabled = false;
                
                if (resObj.success && resObj.data) {
                    renderDigest(resObj.data);
                    alert("Daily Briefing compiled successfully!");
                } else {
                    alert("Failed to compile briefing: " + resObj.error);
                }
            });
        });
    }

    // ==========================================================================
    // Helper Utilities
    // ==========================================================================
    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Disable right-click context menu to prevent inspecting elements/dev tools in production
    document.addEventListener("contextmenu", (e) => {
        e.preventDefault();
    });
});
