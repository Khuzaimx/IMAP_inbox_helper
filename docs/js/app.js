/* ==========================================================================
   InboxHelper Documentation Hub JS Logic
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {

    // ==========================================================================
    // 1. Single Page Application (SPA) Panel Swapping
    // ==========================================================================
    const navLinks = document.querySelectorAll(".nav-link");
    const docPanels = document.querySelectorAll(".doc-panel");

    function switchPanel(targetId) {
        // Remove active class from all sidebar links and panels
        navLinks.forEach(link => link.classList.remove("active"));
        docPanels.forEach(panel => panel.classList.remove("active"));

        // Add active class to selected panel
        const targetPanel = document.getElementById(`panel-${targetId}`);
        if (targetPanel) {
            targetPanel.classList.add("active");
            
            // Highlight matching sidebar link
            const activeLink = document.querySelector(`.nav-link[data-target="${targetId}"]`);
            if (activeLink) {
                activeLink.classList.add("active");
            }

            // Scroll content view smoothly to top
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    }

    // Sidebar navigation clicks
    navLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const target = link.getAttribute("data-target");
            switchPanel(target);
            // Push history state to keep URL hash updated elegantly
            history.pushState(null, null, `#${target}`);
        });
    });

    // Handle inline cross-panel links (e.g. "go to Downloads & Releases" steps)
    document.addEventListener("click", (e) => {
        if (e.target.classList.contains("inner-nav-link")) {
            e.preventDefault();
            const target = e.target.getAttribute("data-target");
            switchPanel(target);
            history.pushState(null, null, `#${target}`);
        }
    });

    // Parse URL hash on direct link visits
    const initialHash = window.location.hash.replace("#", "");
    if (initialHash) {
        switchPanel(initialHash);
    }


    // ==========================================================================
    // 2. Dynamic GitHub Releases Fetcher
    // ==========================================================================
    const releasesContainer = document.getElementById("releases-container");
    const loadingIndicator = document.getElementById("releases-loading");
    const errorFallback = document.getElementById("releases-error");

    async function fetchReleases() {
        try {
            const response = await fetch("https://api.github.com/repos/Khuzaimx/IMAP_inbox_helper/releases");
            if (!response.ok) {
                throw new Error(`GitHub API error: status ${response.status}`);
            }
            
            const releases = await response.json();
            
            if (!releases || releases.length === 0) {
                loadingIndicator.classList.add("hidden");
                releasesContainer.innerHTML = `<div class="alert note"><strong>No Releases Found:</strong> The repository does not contain any published release tags yet.</div>`;
                return;
            }

            // Hide loading indicator
            loadingIndicator.classList.add("hidden");

            // Build release cards dynamically
            releases.forEach((rel, index) => {
                const releaseCard = document.createElement("div");
                releaseCard.className = "release-card";
                
                // Format Publication Date cleanly
                const pubDate = new Date(rel.published_at);
                const formattedDate = pubDate.toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric"
                }) + ` at ${pubDate.toLocaleTimeString("en-US", { hour: '2-digit', minute: '2-digit' })}`;

                // Locate installer executable asset (.exe)
                let setupAssetUrl = null;
                if (rel.assets && rel.assets.length > 0) {
                    const exeAsset = rel.assets.find(asset => asset.name.endsWith(".exe"));
                    if (exeAsset) {
                        setupAssetUrl = exeAsset.browser_download_url;
                    }
                }

                // Fallback to github tag view page if no uploader asset present
                const primaryDownloadUrl = setupAssetUrl || rel.html_url;

                // Simple parser to convert GitHub Release Markdown lists/titles into clean HTML
                let parsedBodyHtml = rel.body ? parseMarkdown(rel.body) : "<p>No release notes provided.</p>";

                releaseCard.innerHTML = `
                    <div class="release-card-header">
                        <div class="release-ver-title">
                            <h3>${escapeHtml(rel.name || rel.tag_name)}</h3>
                            ${index === 0 ? '<span class="version-badge">Latest Stable</span>' : ''}
                        </div>
                        <span class="release-date">${formattedDate}</span>
                    </div>
                    <div class="release-body">
                        ${parsedBodyHtml}
                    </div>
                    <div class="release-actions">
                        <a href="${primaryDownloadUrl}" class="download-btn">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                            Download Setup Wizard (EXE)
                        </a>
                        <a href="${rel.zipball_url}" class="download-btn-secondary">
                            Download Source (ZIP)
                        </a>
                        <a href="${rel.html_url}" target="_blank" class="download-btn-secondary">
                            View on GitHub
                        </a>
                    </div>
                `;
                releasesContainer.appendChild(releaseCard);
            });

        } catch (err) {
            console.error("Error loading releases: ", err);
            loadingIndicator.classList.add("hidden");
            errorFallback.classList.remove("hidden");
        }
    }

    // Trigger API loading
    fetchReleases();


    // ==========================================================================
    // 3. Interactive Sandbox Scoring Engine (Simulator)
    // ==========================================================================
    const sbSlider = document.getElementById("sb-threshold");
    const sbSliderVal = document.getElementById("sb-threshold-val");
    const sbRunBtn = document.getElementById("sb-run-btn");
    const sbResults = document.getElementById("sandbox-results");

    // Keep range slider numeric display synchronized in real-time
    sbSlider.addEventListener("input", () => {
        sbSliderVal.innerText = sbSlider.value;
    });

    sbRunBtn.addEventListener("click", () => {
        // Collect form input parameters
        const sender = document.getElementById("sb-sender").value.trim().toLowerCase();
        const subject = document.getElementById("sb-subject").value.trim().toLowerCase();
        const body = document.getElementById("sb-body").value.trim().toLowerCase();
        
        const isListUnsubscribeSim = document.getElementById("sb-hdr-unsubscribe").checked;
        const isPrecedenceBulkSim = document.getElementById("sb-hdr-bulk").checked;

        const whitelistText = document.getElementById("sb-whitelist").value;
        const blacklistText = document.getElementById("sb-blacklist").value;
        const threshold = parseInt(sbSlider.value);

        // Parse whitelist & blacklist keywords into clean arrays
        const whitelist = whitelistText.split(",").map(s => s.trim().toLowerCase()).filter(s => s.length > 0);
        const blacklist = blacklistText.split(",").map(s => s.trim().toLowerCase()).filter(s => s.length > 0);

        // Core Classifier scoring calculation
        let score = 50; // Starting baseline
        const breakdown = [];
        breakdown.push({ rule: "Baseline Score", pts: "+50", type: "addition" });

        // A. Whitelist Domain/Email Matching Check
        if (whitelist.length > 0) {
            let matchesWhitelist = false;
            for (const item of whitelist) {
                if (sender === item || (item.startsWith("@") && sender.endsWith(item)) || sender.includes(item)) {
                    matchesWhitelist = true;
                    break;
                }
            }
            if (matchesWhitelist) {
                score += 50;
                breakdown.push({ rule: "Sender Domain Whitelisted (High Trust)", pts: "+50", type: "addition" });
            }
        }

        // B. Blacklist Domain/Keyword Matching Check
        if (blacklist.length > 0) {
            let matchesBlacklist = false;
            for (const item of blacklist) {
                if (sender === item || sender.includes(item) || subject.includes(item)) {
                    matchesBlacklist = true;
                    break;
                }
            }
            if (matchesBlacklist) {
                score -= 50;
                breakdown.push({ rule: "Sender Domain / Subject Blacklisted (Low Trust)", pts: "-50", type: "subtraction" });
            }
        }

        // C. Automated Header Flag Reductions
        if (isListUnsubscribeSim) {
            score -= 30;
            breakdown.push({ rule: "Unsubscribe header flag (List-Unsubscribe)", pts: "-30", type: "subtraction" });
        }

        if (isPrecedenceBulkSim) {
            score -= 15;
            breakdown.push({ rule: "Precedence bulk header flag", pts: "-15", type: "subtraction" });
        }

        // D. Sender Address Word Analysis
        const bulkTerms = ["newsletter", "noreply", "no-reply", "marketing", "promo", "offers"];
        let triggeredBulkWord = null;
        for (const term of bulkTerms) {
            if (sender.includes(term)) {
                triggeredBulkWord = term;
                break;
            }
        }
        if (triggeredBulkWord) {
            score -= 25;
            breakdown.push({ rule: `Sender address contains bulk trigger word ("${triggeredBulkWord}")`, pts: "-25", type: "subtraction" });
        }

        // E. Subject Line Positive Keywords
        const transactionTerms = ["invoice", "receipt", "payment", "order", "purchase", "billing"];
        let triggeredTx = null;
        for (const term of transactionTerms) {
            if (subject.includes(term)) {
                triggeredTx = term;
                break;
            }
        }
        if (triggeredTx) {
            score += 25;
            breakdown.push({ rule: `Subject line indicates transactional email ("${triggeredTx}")`, pts: "+25", type: "addition" });
        }

        const criticalTerms = ["urgent", "schedule", "interview", "proposal", "contract", "meeting"];
        let triggeredCrit = null;
        for (const term of criticalTerms) {
            if (subject.includes(term)) {
                triggeredCrit = term;
                break;
            }
        }
        if (triggeredCrit) {
            score += 15;
            breakdown.push({ rule: `Subject line contains critical keyword ("${triggeredCrit}")`, pts: "+15", type: "addition" });
        }

        // F. Body Content Negative Indicators
        if (body.includes("unsubscribe") || body.includes("opt out")) {
            score -= 10;
            breakdown.push({ rule: "Email body text contains unsubscribe keywords", pts: "-10", type: "subtraction" });
        }

        // Keep final score strictly bounded inside standard [0, 100] limits
        let finalScore = Math.max(0, Math.min(100, score));

        // Evaluate routing destination vs threshold
        const isImportant = finalScore >= threshold;

        // Render Results
        document.getElementById("res-score").innerText = finalScore;
        const statusBadge = document.getElementById("res-status");
        
        if (isImportant) {
            statusBadge.innerText = "Important";
            statusBadge.className = "status-badge important";
        } else {
            statusBadge.innerText = "Clutter";
            statusBadge.className = "status-badge clutter";
        }

        // Populate scoring adjustments list
        const listContainer = document.getElementById("res-breakdown");
        listContainer.innerHTML = "";
        
        breakdown.forEach(item => {
            const li = document.createElement("li");
            li.className = item.type;
            li.innerHTML = `
                <span>${item.rule}</span>
                <span class="rule-pts">${item.pts}</span>
            `;
            listContainer.appendChild(li);
        });

        // Unveil Results block smoothly
        sbResults.classList.remove("hidden");
        sbResults.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });


    // ==========================================================================
    // 4. Helper Utilities
    // ==========================================================================

    // Simple markdown-to-HTML formatter specifically optimized for GitHub Release notes
    function parseMarkdown(md) {
        let html = md;
        
        // Escape HTML tags to prevent XSS from source release notes
        html = escapeHtml(html);

        // Format code blocks
        html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        
        // Format inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Format bold tags
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Format bullet points (starts with * or - or +)
        html = html.replace(/^\s*[-*+]\s+(.+)$/gm, '<li>$1</li>');
        
        // Wrap contiguous list items into ul structures
        html = html.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>');
        // Clean duplicate adjacent uls
        html = html.replace(/<\/ul>\s*<ul>/g, '');

        // Format subheadings (e.g. ### Features)
        html = html.replace(/^\s*###\s+(.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^\s*##\s+(.+)$/gm, '<h3>$1</h3>');

        // Convert double linebreaks to paragraphs
        html = html.split('\n\n').map(p => {
            p = p.trim();
            if (!p) return '';
            if (p.startsWith('<ul') || p.startsWith('<pre') || p.startsWith('<h')) return p;
            return `<p>${p}</p>`;
        }).join('\n');

        return html;
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

});
