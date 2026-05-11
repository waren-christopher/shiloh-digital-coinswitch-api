document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("apiForm");
    const loading = document.getElementById("loading");
    const responseSection = document.getElementById("responseSection");
    const responseBox = document.getElementById("responseBox");
    const statusCodeBox = document.getElementById("statusCode");
    const inputFields = document.getElementById("inputFields");

    /* --- MODAL ELEMENTS --- */
    const modal = document.getElementById("customModal");
    const modalConfirmBtn = document.getElementById("modalConfirm");
    const modalCancelBtn = document.getElementById("modalCancel");
    let pendingApiString = null;

    /* ================================
       TRANSACTION DEFAULTS
    ================================= */
    const transactionDefaults = {

        crypto_withdrawal: {
            amount: "",
            assetName: "USDT",
            chain: "TRON",
            address: "binance address",
            subaddress: ""
        },

        inr_withdrawal: {
            amount: "",
            accountNumber_display: "select bank"
        },

        transfer_broker_to_master: {
            amount: "",
            assetName: "USDT",
            fromID: "brokerid",
            toID: "masterid"
        },

        transfer_master_to_broker: {
            amount: "",
            assetName: "INR",
            fromID: "masterid",
            toID: "brokerid"
        },

        buy_market_order: {
            quantity: "",
            bestQuantity: "",
            type: "market",
            side: "BUY",
            instrument: "USDT/INR",
            quantityType: "QUOTE",
            bestQuantityType: "QUOTE",
            username: "shilohdigital_otc"
        },

        buy_limit_order: {
            limitPrice: "",
            quantity: "",
            type: "limit",
            side: "BUY",
            instrument: "USDT/INR",
            quantityType: "QUOTE",
            username: "shilohdigital_otc"
        },

        sell_limit_order: {
            limitPrice: "",
            quantity: "",
            type: "limit",
            side: "SELL",
            instrument: "USDT/INR",
            quantityType: "QUOTE",
            username: "shilohdigital_otc"
        },

        cancel_order: { orderId: "" }
    };

    const optionalFields = ["subaddress"];

    /* ================================
       JSON SYNTAX HIGHLIGHTER
    ================================= */
    function syntaxHighlight(json) {
        json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        return json.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?)/g,
            match => {
                let cls = "json-number";
                if (/^"/.test(match)) cls = /:$/.test(match) ? "json-key" : "json-string";
                else if (/true|false/.test(match)) cls = "json-boolean";
                else if (/null/.test(match)) cls = "json-null";
                return `<span class="${cls}">${match}</span>`;
            }
        );
    }

    /* ================================
       DISPLAY RESPONSE
    ================================= */
    function displayFormattedResponse(rawData, httpStatus, apiName) {

        loading.style.display = "none";
        responseSection.style.display = "block";

        let finalStatus = httpStatus;
        let jsonObject = rawData;

        try {
            if (typeof rawData === "string") jsonObject = JSON.parse(rawData);
            if (jsonObject?.status !== undefined) {
                finalStatus = parseInt(jsonObject.status);
            }
        } catch {}

        const isSuccess = finalStatus === 200;

        statusCodeBox.textContent = finalStatus + (isSuccess ? " OK" : "");
        statusCodeBox.style.color = isSuccess ? "#22c55e" : "#ef4444";
        statusCodeBox.style.borderColor = isSuccess ? "#22c55e" : "#ef4444";

        let isRecentOrders = (apiName === "recent_orders");

        let orders = null;
        if (isRecentOrders && isSuccess) {
            if (Array.isArray(jsonObject?.data)) {
                orders = jsonObject.data;
            } else if (Array.isArray(jsonObject?.data?.data)) {
                orders = jsonObject.data.data;
            }
        }

        if (orders) {
            let html = '<div style="overflow-x:auto;"><table class="nice-table"><thead><tr>' +
                '<th>Order ID</th><th>Instrument</th><th>Side</th><th>Status</th>' +
                '<th>Limit Price</th><th>Quantity</th><th>Filled Qty</th><th>Filled Quote</th>' +
                '<th>Cancelled Qty</th><th>Created At</th></tr></thead><tbody>';
            
            orders.forEach(o => {
                let d = new Date(parseInt(o.createdAt || 0) * 1000).toLocaleString();
                html += `<tr>
                    <td style="white-space: nowrap;">
                        ${o.orderId}
                        <button class="copy-icon-btn" onclick="window.copyText('${o.orderId}')" title="Copy Order ID" style="background: transparent; border: none; cursor: pointer; margin-left: 8px; color: #3b82f6; transition: color 0.2s;">
                            <i class="fas fa-copy"></i>
                        </button>
                    </td>
                    <td>${o.instrument}</td>
                    <td class="${o.side==='BUY'?'text-buy':'text-sell'}">${o.side}</td>
                    <td>${o.status}</td><td>${o.limitPrice}</td><td>${o.quantity}</td>
                    <td>${o.filledQuantity}</td><td>${o.filledQuoteQuantity}</td>
                    <td>${o.cancelledQuantity}</td><td>${d}</td>
                </tr>`;
            });
            html += '</tbody></table></div>';
            responseBox.innerHTML = html;
            return;
        }

        try {
            const jsonString =
                typeof jsonObject === "object"
                    ? JSON.stringify(jsonObject, null, 2)
                    : jsonObject;

            let htmlContent = syntaxHighlight(jsonString);

            htmlContent = htmlContent.replace(
                /<span class="json-key">"orderId":<\/span>\s*<span class="json-string">"(.*?)"<\/span>/g,
                (match, idValue) =>
                    `${match} <button class="copy-icon-btn" onclick="window.copyText('${idValue}')"><i class="fas fa-copy"></i></button>`
            );

            responseBox.innerHTML = htmlContent;

        } catch {
            responseBox.textContent = rawData;
        }
    }

    /* ================================
       API CALL
    ================================= */
    async function performApiCall(formData) {
        
        const apiName = formData.get("api");

        loading.style.display = "block";
        responseSection.style.display = "none";

        const response = await fetch("", {
            method: "POST",
            headers: {
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: formData
        });

        const data = await response.text();
        displayFormattedResponse(data, response.status, apiName);
    }

    function validateRequiredFields(formData) {
        let isValid = true;
        
        document.querySelectorAll('.error-message').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));

        for (let [key, value] of formData.entries()) {
            if (key === "api") continue;
            if (!optionalFields.includes(key) && (!value || value.trim() === "")) {
                const errorDiv = document.getElementById(`err_${key}`);
                const inputEl = document.querySelector(`[name="${key}"]`);
                if (errorDiv) errorDiv.style.display = 'block';
                if (inputEl) inputEl.classList.add('input-error');
                isValid = false;
            }
        }
        
        if (!isValid) {
            const firstError = document.querySelector('.input-error');
            if (firstError) firstError.focus();
        }
        
        return isValid;
    }

    /* ================================
       RENDER INPUTS
    ================================= */
    function renderInputs(apiName, defaults) {

        inputFields.innerHTML = "";

        let apiInput = document.querySelector("input[name='api']");
        if (!apiInput) {
            apiInput = document.createElement("input");
            apiInput.type = "hidden";
            apiInput.name = "api";
            form.prepend(apiInput);
        }
        apiInput.value = apiName;

        for (const [key, value] of Object.entries(defaults)) {

            /* 🔥 INR WITHDRAWAL DROPDOWN */
            if (key === "accountNumber_display") {

                const group = document.createElement("div");
                group.className = "form-group";

                group.innerHTML = `
                    <span class="input-label">
                        ACCOUNT NUMBER <span style="color:#ef4444;"> *</span>
                    </span>

                    <select id="accountSelect" class="account-dropdown">
                        <option value="136628600000041">Shiloh Yes bank</option>
                        <option value="120039711894">Shloh canara bank</option>
                    </select>

                    <input type="hidden" name="accountNumber" id="hiddenAccountNumber" value="311536374533912" />
                    <div id="err_accountNumber" class="error-message">Required</div>
                `;

                inputFields.appendChild(group);

                const select = group.querySelector("#accountSelect");
                const hiddenInput = group.querySelector("#hiddenAccountNumber");

                select.addEventListener("change", () => {
                    hiddenInput.value = select.value;
                });

                continue;
            }

            const isOptional = optionalFields.includes(key);
            const isLocked = ["address", "fromID", "toID"].includes(key);

            const group = document.createElement("div");
            group.className = "form-group";

            group.innerHTML = `
                <span class="input-label">
                    ${key.toUpperCase()}
                    ${isOptional
                        ? "<span style='color:#94a3b8;font-size:0.65rem;'>(optional)</span>"
                        : "<span style='color:#ef4444;'> *</span>"}
                </span>
                <input name="${key}" value="${value}" ${isLocked ? "readonly" : ""} />
                <div id="err_${key}" class="error-message">Required</div>
            `;

            inputFields.appendChild(group);
        }

        inputFields.style.display = "grid";
        const executeBtn = document.getElementById("executeBtn");
        if (executeBtn) executeBtn.style.display = "flex";
        inputFields.scrollIntoView({ behavior: "smooth" });
    }

    /* ================================
       MODAL LOGIC
    ================================= */
    function closeModal() {
        modal.style.display = "none";
        pendingApiString = null;
    }

    modalCancelBtn.addEventListener("click", closeModal);

    modalConfirmBtn.addEventListener("click", () => {
        if (pendingApiString) {
            const fd = new FormData();
            fd.append("api", pendingApiString);
            performApiCall(fd);
        }
        closeModal();
    });

    modal.addEventListener("click", e => {
        if (e.target === modal) closeModal();
    });

    /* ================================
       BUTTON CLICK HANDLER
    ================================= */
    document.addEventListener("click", e => {

        const btn = e.target.closest("[data-api]");
        if (!btn) return;

        document.querySelectorAll(".quick-btn, .transaction-btn")
            .forEach(b => b.classList.remove("active-btn"));

        btn.classList.add("active-btn");

        const api = btn.dataset.api;
        const baseApi = api.split("+")[0];
        const needsConfirm = btn.dataset.confirm === "true";

        if (needsConfirm) {
            pendingApiString = api;
            modal.style.display = "flex";
            return;
        }

        if (btn.classList.contains("quick-btn")) {
            const fd = new FormData();
            fd.append("api", api);
            performApiCall(fd);
            return;
        }

        if (transactionDefaults[baseApi]) {
            renderInputs(api, transactionDefaults[baseApi]);
        }
    });

    /* ================================
       FORM SUBMIT
    ================================= */
    form.addEventListener("submit", e => {
        e.preventDefault();
        const formData = new FormData(form);
        if (!validateRequiredFields(formData)) return;
        performApiCall(formData);
    });

    /* ================================
       COPY HELPER
    ================================= */
    window.copyText = function (text) {
        navigator.clipboard.writeText(text);
    };

});
