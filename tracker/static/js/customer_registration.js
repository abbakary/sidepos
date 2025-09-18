document.addEventListener('DOMContentLoaded', function() {
    // --- Helpers ---
    const wizardContainer = document.getElementById('registrationWizard');
    const rootForm = () => wizardContainer ? wizardContainer.querySelector('form') : null;

    function getCurrentStep() {
        const f = rootForm();
        const si = f ? f.querySelector('input[name="step"]') : null;
        const s = si ? parseInt(si.value || '1', 10) : 1;
        return isNaN(s) ? 1 : s;
    }
    function setCurrentStep(step) {
        const f = rootForm();
        const si = f ? f.querySelector('input[name="step"]') : null;
        if (si) si.value = String(step);
        localStorage.setItem('customerRegCurrentStep', String(step));
        updateStepNavState(step);
    }
    function updateStepNavState(current) {
        const links = document.querySelectorAll('[data-step-link="true"]');
        links.forEach((a) => {
            const url = new URL(a.getAttribute('href'), window.location.origin);
            const stepParam = parseInt(url.searchParams.get('step') || '1', 10);
            a.classList.toggle('disabled', stepParam > current);
            if (stepParam === current) a.classList.add('active'); else a.classList.remove('active');
        });
    }
    function showAlert(type, message) {
        if (!wizardContainer || !message) return;
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show d-flex align-items-center`;
        alert.innerHTML = `<i class="fa ${type==='success'?'fa-check-circle':type==='error'?'fa-times-circle':type==='warning'?'fa-exclamation-triangle':'fa-info-circle'} me-2"></i><div>${message}</div><button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>`;
        wizardContainer.prepend(alert);
    }
    function parseNextStepFromHTML(html) {
        try {
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const stepInput = doc.querySelector('input[name="step"]');
            return stepInput ? parseInt(stepInput.value || '1', 10) : null;
        } catch { return null; }
    }

    // --- AJAX load a step (GET) ---
    async function loadStep(step) {
        const params = new URLSearchParams({ step: String(step), load_step: '1' });
        const res = await fetch(`${window.location.pathname}?${params.toString()}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!res.ok) throw new Error('Failed to load step');
        const data = await res.json();
        if (data.form_html && wizardContainer) {
            wizardContainer.innerHTML = data.form_html;
            // Execute inline and external scripts inside the replaced HTML
            executeScripts(wizardContainer);
            setCurrentStep(step);
            rebindDynamicHandlers();
        }
    }

    // --- AJAX submit current step (POST) ---
    async function submitStep(e) {
        const form = rootForm();
        if (!form) return;
        e.preventDefault();

        const fd = new FormData(form);
        const res = await fetch(window.location.pathname, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: fd
        });
        if (!res.ok) { showAlert('error', 'Network error, please try again'); return; }
        const data = await res.json();

        if (data.message && data.message_type) showAlert(data.message_type, data.message);
        if (data.redirect_url) { window.location.href = data.redirect_url; return; }

        if (data.success) {
            if (data.form_html && wizardContainer) {
                wizardContainer.innerHTML = data.form_html;
                executeScripts(wizardContainer);
                const nextStep = parseNextStepFromHTML(data.form_html) || (getCurrentStep() + 1);
                setCurrentStep(nextStep);
                rebindDynamicHandlers();
            }
        } else {
            // If server returned updated HTML with errors, render it
            if (data.form_html && wizardContainer) {
                wizardContainer.innerHTML = data.form_html;
                executeScripts(wizardContainer);
                rebindDynamicHandlers();
            }
            // Also decorate fields with client-side error highlights if provided
            if (data.errors) {
                Object.keys(data.errors).forEach((name) => {
                    const el = wizardContainer.querySelector(`[name="${name}"]`);
                    if (el) el.classList.add('is-invalid');
                });
                const firstErr = wizardContainer.querySelector('.is-invalid');
                if (firstErr) firstErr.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    // --- Intercept step nav clicks (no full page reload) ---
    function bindStepNav() {
        document.querySelectorAll('[data-step-link="true"]').forEach((a) => {
            a.addEventListener('click', async (ev) => {
                ev.preventDefault();
                const current = getCurrentStep();
                const url = new URL(a.getAttribute('href'), window.location.origin);
                const target = parseInt(url.searchParams.get('step') || '1', 10);
                if (target > current) return; // gating forward navigation
                try { await loadStep(target); } catch (e) { console.error(e); }
            });
        });
    }

    // --- Form submit interception for SPA ---
    function bindFormSubmit() {
        const form = rootForm();
        if (!form) return;
        form.addEventListener('submit', submitStep);
    }

    // --- Enable/disable Next buttons based on selections ---
    function bindIntentServiceEnablers() {
        const nextIntentBtn = document.getElementById('nextStepBtn');
        const intentRadios = wizardContainer.querySelectorAll('input[name="intent"]');
        if (nextIntentBtn && intentRadios.length) {
            function check() {
                let any = false; intentRadios.forEach(r => { if (r.checked) any = true; });
                nextIntentBtn.disabled = !any;
            }
            intentRadios.forEach(r => r.addEventListener('change', check));
            check();
        }
        const nextServiceBtn = document.getElementById('nextServiceBtn');
        const svcRadios = wizardContainer.querySelectorAll('input[name="service_type"]');
        if (nextServiceBtn && svcRadios.length) {
            function check2(){ let any=false; svcRadios.forEach(r=>{ if(r.checked) any=true; }); nextServiceBtn.disabled=!any; }
            svcRadios.forEach(r=>r.addEventListener('change', check2));
            check2();
        }
    }

    function rebindDynamicHandlers() {
        // Rebind handlers after DOM replacement
        bindStepNav();
        bindFormSubmit();
        bindIntentServiceEnablers();
        // Keep existing behaviors
        initializeDynamicBits();
    }

    // --- Existing behaviors (moved to reusable function) ---
    function initializeBrandMapping() {
        const itemNameSelect = document.getElementById('id_item_name');
        if (!itemNameSelect) return {};
        try { const brandsData = itemNameSelect.getAttribute('data-brands'); return brandsData ? JSON.parse(brandsData) : {}; }
        catch (e) { console.error('Error parsing brand mapping:', e); return {}; }
    }
    let brandMapping = initializeBrandMapping();
    function setupBrandUpdate() {
        const itemNameSelect = document.getElementById('id_item_name');
        const brandSelect = document.getElementById('id_brand');
        if (!itemNameSelect || !brandSelect) return;
        itemNameSelect.addEventListener('change', function() {
            const brandName = brandMapping[this.value];
            if (brandName) {
                for (let i = 0; i < brandSelect.options.length; i++) {
                    if (brandSelect.options[i].text === brandName || brandSelect.options[i].value === brandName) {
                        brandSelect.selectedIndex = i; break;
                    }
                }
            }
        });
    }
    function initializePhoneMask() {
        const phoneInput = document.querySelector('input[name="phone"]');
        if (phoneInput) {
            phoneInput.addEventListener('input', function(e) {
                let value = e.target.value.replace(/\D/g, '');
                if (value.length > 13) value = value.substring(0, 13);
                e.target.value = value;
            });
        }
    }
    function toggleCustomerTypeFields() {
        const customerTypeSelect = document.querySelector('select[name="customer_type"]');
        if (!customerTypeSelect) return;
        const selectedType = customerTypeSelect.value;
        const organizationField = document.getElementById('organization-field');
        const taxField = document.getElementById('tax-field');
        const personalSubtypeField = document.getElementById('personal-subtype-field');
        [organizationField, taxField, personalSubtypeField].forEach(field => {
            if (field) {
                field.style.display = 'none';
                field.querySelectorAll('input, select, textarea').forEach(i => i.removeAttribute('required'));
            }
        });
        if (selectedType === 'personal') {
            if (personalSubtypeField) { personalSubtypeField.style.display = 'block'; const s = personalSubtypeField.querySelector('select'); if (s) s.setAttribute('required','required'); }
        } else if (['government','ngo','company'].includes(selectedType)) {
            if (organizationField) { organizationField.style.display = 'block'; const i = organizationField.querySelector('input'); if (i) i.setAttribute('required','required'); }
            if (taxField) { taxField.style.display = 'block'; const i = taxField.querySelector('input'); if (i) i.setAttribute('required','required'); }
        }
        setTimeout(() => {
            [organizationField, taxField, personalSubtypeField].forEach(field => {
                if (field && field.style.display === 'block') {
                    field.classList.add('animate-in'); setTimeout(() => field.classList.remove('animate-in'), 400);
                }
            });
        }, 50);
    }
    function bindCustomerTypeToggle(){ const s=document.querySelector('select[name="customer_type"]'); if (s){ s.addEventListener('change', toggleCustomerTypeFields); toggleCustomerTypeFields(); } }

    // duplicate check used only on explicit non-AJAX fallback; keep as-is
    async function checkDuplicateCustomer() {
        const form = rootForm(); if (!form) return null;
        const nameEl = form.querySelector('#id_full_name');
        const phoneEl = form.querySelector('#id_phone');
        const typeEl = form.querySelector('#id_customer_type');
        const orgEl = form.querySelector('#id_organization_name');
        const taxEl = form.querySelector('#id_tax_number');
        if (!nameEl || !phoneEl) return null;
        const full_name = (nameEl.value || '').trim();
        const phone = (phoneEl.value || '').trim();
        const customer_type = typeEl ? (typeEl.value || '').trim() : '';
        const organization_name = orgEl ? (orgEl.value || '').trim() : '';
        const tax_number = taxEl ? (taxEl.value || '').trim() : '';
        if (!full_name || !phone) return null;
        const params = new URLSearchParams({ full_name, phone, customer_type, organization_name, tax_number });
        const res = await fetch(`/api/customers/check-duplicate/?${params.toString()}`, { headers: { 'Accept': 'application/json' }});
        if (!res.ok) return null; return res.json();
    }

    function initializeLocalSave() {
        const form = rootForm(); if (!form) return;
        function saveFormData() {
            const fd = new FormData(form); const obj = {}; fd.forEach((v,k)=>{ obj[k]=v; });
            localStorage.setItem('customerRegistrationData', JSON.stringify(obj));
        }
        function loadFormData() {
            const saved = localStorage.getItem('customerRegistrationData'); if (!saved) return;
            try { const obj = JSON.parse(saved); Object.keys(obj).forEach(k => { const el=form.querySelector(`[name="${k}"]`); if (!el) return; if (el.type==='checkbox'||el.type==='radio'){ el.checked = obj[k] === 'true' || obj[k] === el.value; } else { el.value = obj[k]; } }); }
            catch(e){ console.error('Error loading form data:', e); localStorage.removeItem('customerRegistrationData'); }
        }
        loadFormData();
        form.addEventListener('input', saveFormData);
        form.addEventListener('submit', () => localStorage.removeItem('customerRegistrationData'));
    }

    function initializeDynamicBits(){
        brandMapping = initializeBrandMapping();
        setupBrandUpdate();
        initializePhoneMask();
        bindCustomerTypeToggle();
        initializeLocalSave();
        // tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); });
    }

    // Initial binds
    bindStepNav();
    bindFormSubmit();
    bindIntentServiceEnablers();
    initializeDynamicBits();
    updateStepNavState(getCurrentStep());
});
