document.addEventListener('DOMContentLoaded', function() {
    // Initialize brand mapping from item name to brand
    function initializeBrandMapping() {
        const itemNameSelect = document.getElementById('id_item_name');
        if (!itemNameSelect) return null;
        
        try {
            const brandsData = itemNameSelect.getAttribute('data-brands');
            return brandsData ? JSON.parse(brandsData) : {};
        } catch (e) {
            console.error('Error parsing brand mapping:', e);
            return {};
        }
    }
    
    const brandMapping = initializeBrandMapping();
    
    // Update brand dropdown when item is selected
    function setupBrandUpdate() {
        const itemNameSelect = document.getElementById('id_item_name');
        const brandSelect = document.getElementById('id_brand');
        
        if (!itemNameSelect || !brandSelect) return;
        
        itemNameSelect.addEventListener('change', function() {
            const selectedItem = this.value;
            const brandName = brandMapping[selectedItem];
            
            if (brandName) {
                // Find and select the brand in the dropdown
                for (let i = 0; i < brandSelect.options.length; i++) {
                    if (brandSelect.options[i].text === brandName) {
                        brandSelect.selectedIndex = i;
                        break;
                    }
                }
            }
        });
    }
    
    // Initialize brand update functionality
    setupBrandUpdate();
    
    // Auto-format phone number
    const phoneInput = document.querySelector('input[name="phone"]');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 13) value = value.substring(0, 13);
            e.target.value = value;
        });
    }

    // Customer type dynamic fields
    const customerTypeSelect = document.querySelector('select[name="customer_type"]');
    if (customerTypeSelect) {
        function toggleCustomerTypeFields() {
            const selectedType = customerTypeSelect.value;
            
            // Get conditional field elements
            const organizationField = document.getElementById('organization-field');
            const taxField = document.getElementById('tax-field');
            const personalSubtypeField = document.getElementById('personal-subtype-field');
            
            // Hide all conditional fields first
            [organizationField, taxField, personalSubtypeField].forEach(field => {
                if (field) {
                    field.style.display = 'none';
                    // Remove required attribute from hidden fields
                    const inputs = field.querySelectorAll('input, select, textarea');
                    inputs.forEach(input => input.removeAttribute('required'));
                }
            });

            // Show relevant fields based on customer type
            if (selectedType === 'personal') {
                // Show personal subtype field for personal customers
                if (personalSubtypeField) {
                    personalSubtypeField.style.display = 'block';
                    const subtypeSelect = personalSubtypeField.querySelector('select');
                    if (subtypeSelect) subtypeSelect.setAttribute('required', 'required');
                }
            } else if (['government', 'ngo', 'company'].includes(selectedType)) {
                // Show organization and tax fields for organizational customers
                if (organizationField) {
                    organizationField.style.display = 'block';
                    const orgInput = organizationField.querySelector('input');
                    if (orgInput) orgInput.setAttribute('required', 'required');
                }
                if (taxField) {
                    taxField.style.display = 'block';
                    const taxInput = taxField.querySelector('input');
                    if (taxInput) taxInput.setAttribute('required', 'required');
                }
            }
            // For 'bodaboda' type, no additional fields are required
            
            // Add visual feedback for field changes with smooth animations
            setTimeout(() => {
                [organizationField, taxField, personalSubtypeField].forEach(field => {
                    if (field && field.style.display === 'block') {
                        field.classList.add('animate-in');
                        // Remove animation class after animation completes
                        setTimeout(() => field.classList.remove('animate-in'), 400);
                    }
                });
            }, 50);
        }

        // Initialize on page load
        toggleCustomerTypeFields();
        
        // Handle changes
        customerTypeSelect.addEventListener('change', toggleCustomerTypeFields);
    }

    // Intent selection enhancement
    const intentCards = document.querySelectorAll('.intent-card');
    const intentRadios = document.querySelectorAll('input[name="intent"]');
    
    if (intentCards.length > 0) {
        // Add click handlers to cards
        intentCards.forEach(card => {
            card.addEventListener('click', function() {
                const radio = this.querySelector('input[type="radio"]');
                if (radio) {
                    radio.checked = true;
                    updateIntentCardStyles();
                }
            });
        });

        // Add change handlers to radio buttons
        intentRadios.forEach(radio => {
            radio.addEventListener('change', updateIntentCardStyles);
        });

        function updateIntentCardStyles() {
            intentCards.forEach(card => {
                const radio = card.querySelector('input[type="radio"]');
                if (radio && radio.checked) {
                    card.classList.add('selected');
                } else {
                    card.classList.remove('selected');
                }
            });
        }

        // Initialize on page load
        updateIntentCardStyles();
    }

    // Service and Sales card selection
    const serviceCards = document.querySelectorAll('.service-check-card');
    const salesCards = document.querySelectorAll('.sales-check-card');
    
    function handleCheckCardClick(cards) {
        cards.forEach(card => {
            card.addEventListener('click', function() {
                const checkbox = this.querySelector('input[type="checkbox"]');
                const radio = this.querySelector('input[type="radio"]');
                
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                } else if (radio) {
                    radio.checked = true;
                }
                
                updateCheckCardStyles(cards);
            });
        });
    }
    
    function updateCheckCardStyles(cards) {
        cards.forEach(card => {
            const input = card.querySelector('input[type="checkbox"], input[type="radio"]');
            if (input && input.checked) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });
    }
    
    if (serviceCards.length > 0) {
        handleCheckCardClick(serviceCards);
        updateCheckCardStyles(serviceCards);
    }
    
    if (salesCards.length > 0) {
        handleCheckCardClick(salesCards);
        updateCheckCardStyles(salesCards);
    }

    // Dynamic service type loading
    const serviceTypeRadios = document.querySelectorAll('input[name="service_type"]');
    const serviceDetails = document.getElementById('service-details');
    
    if (serviceTypeRadios.length && serviceDetails) {
        serviceTypeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                if (this.checked) {
                    const serviceType = this.value;
                    fetch(`/service-form/${serviceType}/`)
                        .then(response => response.text())
                        .then(html => {
                            serviceDetails.innerHTML = html;
                            // Re-initialize any dynamic elements if needed
                        })
                        .catch(error => console.error('Error loading service form:', error));
                }
            });
        });
    }

    // Form validation + duplicate customer check (Step 1) + AJAX navigation/submission
    const wizardContainer = document.getElementById('registrationWizard');
    const form = wizardContainer ? wizardContainer.querySelector('form') : document.querySelector('form');

    async function checkDuplicateCustomer() {
        const nameEl = document.getElementById('id_full_name');
        const phoneEl = document.getElementById('id_phone');
        const typeEl = document.getElementById('id_customer_type');
        const orgEl = document.getElementById('id_organization_name');
        const taxEl = document.getElementById('id_tax_number');
        if (!nameEl || !phoneEl) return null;
        const full_name = (nameEl.value || '').trim();
        const phone = (phoneEl.value || '').trim();
        const customer_type = typeEl ? (typeEl.value || '').trim() : '';
        const organization_name = orgEl ? (orgEl.value || '').trim() : '';
        const tax_number = taxEl ? (taxEl.value || '').trim() : '';
        if (!full_name || !phone) return null;
        const params = new URLSearchParams({ full_name, phone, customer_type, organization_name, tax_number });
        const res = await fetch(`/api/customers/check-duplicate/?${params.toString()}`, { headers: { 'Accept': 'application/json' }});
        if (!res.ok) return null;
        return res.json();
    }

    function showExistingCustomerModal(data) {
        const modalEl = document.getElementById('existingCustomerModal');
        if (!modalEl || !data || !data.customer) return;
        const c = data.customer;
        document.getElementById('existingCustomerName').textContent = c.full_name || '';
        document.getElementById('existingCustomerCode').textContent = c.code || '';
        document.getElementById('existingCustomerPhone').textContent = c.phone || '';
        document.getElementById('existingCustomerType').textContent = (c.customer_type || 'personal');
        document.getElementById('existingCustomerOrg').textContent = c.organization_name || '-';
        document.getElementById('existingCustomerTax').textContent = c.tax_number || '-';
        document.getElementById('existingCustomerEmail').textContent = c.email || '-';
        document.getElementById('existingCustomerVisits').textContent = c.total_visits != null ? c.total_visits : '-';
        document.getElementById('existingCustomerAddress').textContent = c.address || '-';
        const orderBtn = document.getElementById('existingCustomerCreateOrderBtn');
        const viewBtn = document.getElementById('existingCustomerViewBtn');
        if (orderBtn) orderBtn.setAttribute('href', c.create_order_url);
        if (viewBtn) viewBtn.setAttribute('href', c.detail_url);
        const bsModal = new bootstrap.Modal(modalEl);
        bsModal.show();
    }

    // Helper: replace wizard HTML with smooth transition
    function replaceWizardHtml(html) {
        if (!wizardContainer) return;
        wizardContainer.style.opacity = '0.4';
        wizardContainer.style.transition = 'opacity 150ms ease';
        setTimeout(() => {
            wizardContainer.innerHTML = html;
            wizardContainer.style.opacity = '1';
            // Re-bind handlers after DOM replace
            bindWizardHandlers();
        }, 150);
    }

    // AJAX navigate to a step (GET)
    async function ajaxLoadStep(url) {
        const u = new URL(url, window.location.origin);
        u.searchParams.set('load_step', '1');
        const res = await fetch(u.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!res.ok) return;
        const data = await res.json();
        if (data.form_html) replaceWizardHtml(data.form_html);
        // Update URL without reload so back/forward works
        history.pushState({}, '', url);
    }

    // AJAX submit the wizard form (POST)
    async function ajaxSubmitForm(currentForm) {
        const formData = new FormData(currentForm);
        const res = await fetch(window.location.href, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
            return;
        }
        if (data.form_html) replaceWizardHtml(data.form_html);
        if (data.message && data.message_type) {
            // Optionally show toast or inline alert; minimal inline alert here
            const alert = document.createElement('div');
            alert.className = `alert alert-${data.message_type} mt-2`;
            alert.textContent = data.message;
            wizardContainer.prepend(alert);
            setTimeout(() => alert.remove(), 3500);
        }
    }

    // Bind click handlers for step links and submit handler
    function bindWizardHandlers() {
        const container = document.getElementById('registrationWizard');
        if (!container) return;

        // Intercept step navigation links
        container.querySelectorAll('[data-step-link="true"]').forEach(a => {
            a.addEventListener('click', function(e) {
                e.preventDefault();
                ajaxLoadStep(this.href);
            });
        });

        // Intercept form submission for all steps
        const currentForm = container.querySelector('form');
        if (currentForm) {
            currentForm.addEventListener('submit', async function(e) {
                // Basic required validation
                let isValid = true;
                const requiredFields = currentForm.querySelectorAll('[required]');
                requiredFields.forEach(field => {
                    if (!field.value || (field.type === 'checkbox' && !field.checked)) {
                        field.classList.add('is-invalid');
                        isValid = false;
                    } else {
                        field.classList.remove('is-invalid');
                    }
                });
                if (!isValid) {
                    e.preventDefault();
                    const firstInvalid = currentForm.querySelector('.is-invalid');
                    if (firstInvalid) firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    return;
                }

                const stepInput = currentForm.querySelector('input[name="step"]');
                const currentStep = stepInput ? parseInt(stepInput.value, 10) : null;

                // For step 1, check duplicates before progressing
                if (currentStep === 1) {
                    e.preventDefault();
                    const result = await checkDuplicateCustomer();
                    if (result && result.exists) {
                        showExistingCustomerModal(result);
                        return;
                    }
                    await ajaxSubmitForm(currentForm);
                    return;
                }

                // Default: AJAX submit
                e.preventDefault();
                await ajaxSubmitForm(currentForm);
            });
        }
    }

    // Initial bind on first page load
    bindWizardHandlers();

    // Auto-save form data
    function saveFormData() {
        if (!form) return;
        
        const formData = new FormData(form);
        const formObject = {};
        formData.forEach((value, key) => {
            formObject[key] = value;
        });
        
        localStorage.setItem('customerRegistrationData', JSON.stringify(formObject));
    }

    // Load saved form data
    function loadFormData() {
        const savedData = localStorage.getItem('customerRegistrationData');
        if (!savedData) return;
        
        try {
            const formData = JSON.parse(savedData);
            Object.keys(formData).forEach(key => {
                const element = form.querySelector(`[name="${key}"]`);
                if (element) {
                    if (element.type === 'checkbox' || element.type === 'radio') {
                        element.checked = formData[key] === 'true' || formData[key] === element.value;
                    } else {
                        element.value = formData[key];
                    }
                }
            });
        } catch (e) {
            console.error('Error loading form data:', e);
            localStorage.removeItem('customerRegistrationData');
        }
    }

    // Set up auto-save
    if (form) {
        // Load saved data on page load
        loadFormData();
        
        // Save on input change
        form.addEventListener('input', saveFormData);
        
        // Clear saved data on successful form submission
        form.addEventListener('submit', function() {
            localStorage.removeItem('customerRegistrationData');
        });
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
