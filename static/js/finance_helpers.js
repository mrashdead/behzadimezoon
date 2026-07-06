(() => {
  const el = (s, ctx=document) => ctx.querySelector(s);
  const elAll = (s, ctx=document) => Array.from(ctx.querySelectorAll(s));

  function getCookie(name){
    let cookieValue = null; if (document.cookie && document.cookie !== ''){const cookies = document.cookie.split(';'); for (let i=0;i<cookies.length;i++){const c = cookies[i].trim(); if (c.substring(0, name.length+1) === name+'='){cookieValue = decodeURIComponent(c.substring(name.length+1)); break;}}}
    return cookieValue;
  }

  function showToast(message, variant='info', timeout=4000){
    if (window.UIHelpers && typeof UIHelpers.showToast === 'function') return UIHelpers.showToast(message, variant);
    const containerId = 'financeToastContainer';
    let container = document.getElementById(containerId);
    if (!container){ container = document.createElement('div'); container.id = containerId; container.className = 'app-toast-stack'; document.body.appendChild(container); }
    const toast = document.createElement('div');
    toast.className = `app-toast app-toast--${variant}`;
    toast.innerHTML = `<div class="app-toast__content"><div class="app-toast__icon">i</div><div class="app-toast__body"><div class="app-toast__title">${variant}</div><div class="app-toast__message">${message}</div></div><button class="app-toast__close">✕</button></div>`;
    container.appendChild(toast);
    setTimeout(()=>{ toast.classList.add('is-visible'); }, 10);
    function remove(){ toast.classList.add('is-hiding'); setTimeout(()=>toast.remove(), 320); }
    toast.querySelector('.app-toast__close').addEventListener('click', remove);
    setTimeout(remove, timeout);
  }

  async function fetchHtmlInto(url, targetEl){
    if (!targetEl) return;
    targetEl.innerHTML = `<div class="d-flex justify-content-center py-5"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>`;
    try{
      const res = await fetch(url);
      if (!res.ok) { targetEl.innerHTML = '<div class="text-danger text-center py-3">خطا در بارگذاری</div>'; return; }
      const html = await res.text();
      
      // Clean up old content first
      targetEl.innerHTML = '';
      
      // Create a container to parse HTML
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      
      // Extract main content (excluding nested modals)
      const mainContent = tmp.querySelector('.card') || tmp.firstElementChild;
      if (mainContent) {
        targetEl.appendChild(mainContent.cloneNode(true));
      } else {
        targetEl.innerHTML = html;
      }
      
      // Extract and execute scripts separately
      const scripts = tmp.querySelectorAll('script');
      scripts.forEach(s => {
        try {
          const newScript = document.createElement('script');
          newScript.textContent = s.textContent;
          targetEl.appendChild(newScript);
        } catch(e) {
          console.warn('fragment script error', e);
        }
      });
    }catch(e){
      targetEl.innerHTML = '<div class="text-danger text-center py-3">خطا در ارتباط</div>';
      console.error('fetchHtmlInto error:', e);
    }
  }

  async function submitFormAjax(form, opts={}){
    if (!form) return;
    const submitBtn = form.querySelector('[type=submit]'); if (submitBtn) submitBtn.disabled = true;
    const data = new URLSearchParams(new FormData(form));
    try{
      const res = await fetch(form.action, {method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken')}, body: data});
      const json = await res.json();
      if (!res.ok || json.error){ if (json.error) showToast(typeof json.error === 'string' ? json.error : JSON.stringify(json.error), 'danger'); return json; }
      showToast(json.message || 'عملیات با موفقیت انجام شد', 'success');
      if (opts.onSuccess) opts.onSuccess(json);
      return json;
    }catch(e){ showToast('خطا در ارتباط', 'danger'); return {error: 'network'}; }
    finally{ if (submitBtn) submitBtn.disabled = false; }
  }

  function initList(){
    elAll('.open-financial-modal').forEach(btn=>{
      btn.addEventListener('click', (e)=>{
        e.preventDefault();
        const url = btn.dataset.url;
        const modalEl = el('#financialModal');
        const body = el('#financialModalBody');
        if (!modalEl || !body) return;
        
        // Clean up any existing modal state
        const existingModal = bootstrap.Modal.getInstance(modalEl);
        if (existingModal) {
          existingModal.hide();
          setTimeout(() => {
            body.innerHTML = '';
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
            fetchHtmlInto(url, body);
          }, 300);
        } else {
          const modal = new bootstrap.Modal(modalEl);
          modal.show();
          fetchHtmlInto(url, body);
        }
      });
    });
    
    // Handle modal cleanup on hide
    const modalEl = el('#financialModal');
    if (modalEl) {
      modalEl.addEventListener('hidden.bs.modal', function(){
        const body = el('#financialModalBody');
        if (body) {
          body.innerHTML = '<div class="d-flex justify-content-center py-5"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        }
      });
    }
  }

  window.FinanceHelpers = { showToast, fetchHtmlInto, submitFormAjax, initList };
  document.addEventListener('DOMContentLoaded', ()=>{ try{ initList(); }catch(e){ console.warn('FinanceHelpers init failed', e); } });
})();
