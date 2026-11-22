(() => {
  const path = location.pathname;
  const workspace = path === '/' || path === '/index.html';
  const home = '/';
  const items = [['/', 'Workspace', '签章工作台'], ['/seals.html', 'Seal library', '印章管理'], ['/certificates.html', 'Certificates', '证书管理'], ['/verify.html', 'Verify PDF', '验证 PDF'], ['/account.html', 'Account', '账户设置']];
  const header = document.createElement('header');
  header.className = 'app-header';
  header.innerHTML = `<a class="brand" href="${home}"><span class="brand-symbol">b</span>BSign <span class="brand-cn">必签</span></a><nav class="header-end app-nav" aria-label="Main navigation / 主导航"><a class="auth-home" href="${home}" data-en="← Workspace" data-zh="← 返回工作台">← Workspace</a>${items.map(([url,en,zh])=>`<a class="app-nav-link" href="${url}" ${path===url||(url==='/'&&workspace)?'aria-current="page"':''} data-en="${en}" data-zh="${zh}">${en}</a>`).join('')}<button id="account" class="quiet app-user" type="button" title="Account settings / 账户设置" hidden></button><button id="logout" class="quiet" type="button" hidden data-en="Sign out" data-zh="退出">Sign out</button><a id="nav-signin" class="app-nav-link" href="/" hidden data-en="Sign in" data-zh="登录">Sign in</a><button id="lang" class="quiet" type="button">中文</button></nav>`;
  document.currentScript.replaceWith(header);
  const accountButton=document.getElementById('account');
  const avatar=()=>accountButton.dataset.initial=Array.from(accountButton.textContent.trim())[0]||'B';
  new MutationObserver(avatar).observe(accountButton,{childList:true,characterData:true,subtree:true});avatar();
  if (!workspace) {
    let csrf = '';
    document.getElementById('account').onclick=()=>location.assign('/account.html');
    document.getElementById('logout').onclick=async()=>{
      const button=document.getElementById('logout');button.disabled=true;
      try { const response=await fetch('/api/logout',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}'});if(!response.ok)throw Error();location.assign('/'); }
      catch { alert(document.documentElement.lang==='zh-CN'?'退出失败，请刷新页面后重试。':'Could not sign out. Refresh and try again.');button.disabled=false; }
    };
    fetch('/api/me',{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(q=>{
      if(!q){document.getElementById('nav-signin').hidden=false;return;}
      csrf=q.csrf;document.getElementById('account').textContent=q.user.name;document.getElementById('account').hidden=false;document.getElementById('logout').hidden=false;
    }).catch(()=>{document.getElementById('nav-signin').hidden=false;});
  }
})();
