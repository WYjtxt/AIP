/* Public certificate help. This file never reads login tokens or installs certificates. */
(function (root) {
  'use strict';
  var CERTIFICATE = {
    name: 'dispatch-root-ca.cer',
    subject: "CN=AI Platform Root CA, O=AI Platform",
    commonName: "AI Platform Root CA",
    sha256: "F93DFACCC0866045D6612D59B989F1E2A4F495DA61FFB62FF8523D4C5A79FE78",
    notBeforeUtc: "2026-11-19T08:36:28Z",
    notAfterUtc: "2036-11-16T08:36:28Z",
    url: '/static/certificates/dispatch-root-ca.cer',
    bundleUrl: '/static/certificates/dispatch-certificate-windows.zip',
    scriptUrl: '/static/certificates/install-dispatch-certificate.ps1'
  };
  var SEEN_KEY = 'aimonitor.certificate-help.viewed.' + CERTIFICATE.sha256;
  var owner = null, verified = false, verification = null, notice = null, modal = null, focusBeforeOpen = null;
  var shownInMemory = false;

  function el(tag, className, text) {
    var item = root.document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = String(text);
    return item;
  }
  function button(text, className, action) {
    var item = el('button', 'aimcert-button' + (className ? ' ' + className : ''), text);
    item.type = 'button';
    if (action) item.addEventListener('click', action);
    return item;
  }
  function download(text, url, file, className) {
    var link = el('a', 'aimcert-button' + (className ? ' ' + className : ''), text);
    link.href = url; link.download = file;
    return link;
  }
  function windows() {
    var nav = root.navigator || {};
    return /Win/i.test((nav.userAgentData && nav.userAgentData.platform) || nav.platform || nav.userAgent || '');
  }
  function publicActivationPage(vm) {
    var path = vm && vm.$route && String(vm.$route.path || '').split(/[?#]/)[0].replace(/\/+$/, '');
    return path === '/activatebywjj' || path === '/activate2';
  }
  function hasViewed() {
    if (shownInMemory) return true;
    try { return root.localStorage.getItem(SEEN_KEY) === '1'; }
    catch (_) { return false; }
  }
  function markViewed() {
    shownInMemory = true;
    try { root.localStorage.setItem(SEEN_KEY, '1'); } catch (_) { /* Storage may be disabled. */ }
  }
  function removeNotice() {
    if (notice && notice.parentNode) notice.parentNode.removeChild(notice);
    notice = null;
  }
  function close() {
    if (!modal) return;
    var current = modal; modal = null;
    if (typeof current.close === 'function' && current.open) current.close();
    if (current.parentNode) current.parentNode.removeChild(current);
    if (focusBeforeOpen && root.document.contains(focusBeforeOpen)) focusBeforeOpen.focus();
    focusBeforeOpen = null;
  }
  function installationCommand() {
    // Fixed interactive commands only: choose a local public CER, verify, then import.
    // No remote download, dynamic script evaluation, execution-policy changes or private keys.
    return '& { ' + [
      "$ErrorActionPreference='Stop'",
      'Add-Type -AssemblyName System.Windows.Forms',
      '$certificatePicker=New-Object System.Windows.Forms.OpenFileDialog',
      "$certificatePicker.Filter='Certificate (*.cer)|*.cer'",
      "$certificatePicker.Title='Select the downloaded dispatch-root-ca.cer'",
      "if($certificatePicker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK){Write-Host 'Cancelled: no certificate was installed.';return}",
      '$certificatePath=$certificatePicker.FileName',
      "if((Get-FileHash -LiteralPath $certificatePath -Algorithm SHA256).Hash -cne '" + CERTIFICATE.sha256 + "'){throw 'SHA256 mismatch. Nothing was installed.'}",
      '$certificateObject=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList $certificatePath',
      "if($certificateObject.Subject -cne '" + CERTIFICATE.subject + "'){throw 'Certificate subject mismatch. Nothing was installed.'}",
      "if($certificateObject.HasPrivateKey){throw 'A public certificate without a private key is required.'}",
      "$certificateStorePath='Cert:\\CurrentUser\\Root\\'+$certificateObject.Thumbprint",
      "if(Test-Path -LiteralPath $certificateStorePath){Write-Host 'This certificate is already trusted for the current Windows user.';return}",
      "Import-Certificate -FilePath $certificatePath -CertStoreLocation 'Cert:\\CurrentUser\\Root' | Out-Null",
      "if(-not(Test-Path -LiteralPath $certificateStorePath)){throw 'Installation was not completed. The trust confirmation may have been cancelled.'}",
      "Write-Host 'Certificate installed for the current Windows user. Restart the browser and open the HTTPS address.'"
    ].join('; ') + ' }';
  }
  function copy(text, input, message) {
    function fallback() {
      if (!input) return false;
      input.focus(); input.select();
      try { return root.document.execCommand('copy'); } catch (_) { return false; }
    }
    if (root.navigator && root.navigator.clipboard && root.navigator.clipboard.writeText) {
      return root.navigator.clipboard.writeText(text).then(function () {
        message.textContent = '已复制。请在普通 Windows PowerShell 窗口中粘贴运行，并选择已下载的证书。';
      }, function () {
        message.textContent = fallback() ? '已复制安装命令。' : '无法自动复制，请选中下方命令并手动复制。';
      });
    }
    message.textContent = fallback() ? '已复制安装命令。' : '无法自动复制，请选中下方命令并手动复制。';
    return Promise.resolve();
  }
  function step(number, title, text) {
    var row = el('li', 'aimcert-step'), copy = el('div', 'aimcert-step-copy');
    row.appendChild(el('span', 'aimcert-step-number', number));
    copy.appendChild(el('h3', '', title)); copy.appendChild(el('p', '', text)); row.appendChild(copy);
    return {row:row, copy:copy};
  }
  function metadata(label, value, code) {
    var row = el('div', 'aimcert-metadata-row');
    row.appendChild(el('dt', '', label)); row.appendChild(el('dd', code ? 'aimcert-fingerprint' : '', value));
    return row;
  }
  function openVerified() {
    if (!owner || !verified) return false;
    removeNotice(); markViewed();
    if (modal) { if (modal.focus) modal.focus(); return true; }
    focusBeforeOpen = root.document.activeElement;
    var dialog = el('dialog', 'aimcert-dialog');
    dialog.setAttribute('aria-labelledby', 'aimcert-title');
    dialog.setAttribute('aria-describedby', 'aimcert-description');
    var header = el('div', 'aimcert-dialog-header'), heading = el('div');
    heading.appendChild(el('p', 'aimcert-eyebrow', '帮助中心 · HTTPS 安全连接'));
    var title = el('h2', '', '安装内网访问证书'); title.id = 'aimcert-title'; heading.appendChild(title);
    var description = el('p', '', '安装前请核对当前根证书的主题、SHA256 和有效期；已信任同一指纹的证书无需重复导入。'); description.id = 'aimcert-description'; heading.appendChild(description);
    var closeButton = button('×', 'aimcert-close', close); closeButton.setAttribute('aria-label', '关闭证书安装帮助');
    header.appendChild(heading); header.appendChild(closeButton); dialog.appendChild(header);
    var body = el('div', 'aimcert-dialog-body');
    var status = el('div', 'aimcert-status', '网页无法读取此电脑的证书存储，也不会自动执行安装。已安装本页新指纹对应的根证书，无需重复操作。');
    body.appendChild(status);
    body.appendChild(el('p', 'aimcert-muted', '首次访问若因尚未信任证书而无法打开平台，请由管理员离线提供安装包或统一下发证书，无需绕过浏览器安全告警。'));
    var platform = el('div', 'aimcert-platform');
    platform.appendChild(el('strong', '', 'Windows 推荐方式'));
    platform.appendChild(el('span', '', 'Windows 10 / 11 · Windows PowerShell 5.1 或更高版本 · Chrome / Edge'));
    body.appendChild(platform);
    var steps = el('ol', 'aimcert-steps');
    var first = step('1', '下载公开根证书', '保存下方 .cer 文件。核对证书名称和 SHA256 后，再进行安装。');
    var firstActions = el('div', 'aimcert-actions');
    firstActions.appendChild(download('下载证书 .cer', CERTIFICATE.url, CERTIFICATE.name, 'aimcert-button-primary'));
    first.copy.appendChild(firstActions); steps.appendChild(first.row);
    var second = step('2', '复制命令，在 PowerShell 中运行', '打开普通 Windows PowerShell 窗口，粘贴命令。文件选择窗口出现后，选择刚下载的 dispatch-root-ca.cer；命令会先核验指纹和名称，再导入当前用户的受信任根证书。');
    var command = installationCommand();
    var commandInput = el('textarea', 'aimcert-command'); commandInput.value = command; commandInput.readOnly = true; commandInput.rows = 4;
    commandInput.setAttribute('aria-label', 'Windows 当前用户证书安装命令'); commandInput.spellcheck = false;
    var feedback = el('p', 'aimcert-copy-feedback', '仅作用于当前 Windows 用户，不要求以管理员身份打开 PowerShell。');
    feedback.setAttribute('role', 'status'); feedback.setAttribute('aria-live', 'polite');
    var secondActions = el('div', 'aimcert-actions');
    secondActions.appendChild(button('复制安装命令', 'aimcert-button-primary', function () { copy(command, commandInput, feedback); }));
    second.copy.appendChild(secondActions); second.copy.appendChild(commandInput); second.copy.appendChild(feedback); steps.appendChild(second.row);
    var third = step('3', '确认并重新打开浏览器', '如系统弹出信任提示，核对证书后确认。命令显示 installed 或 already trusted 后，关闭并重新打开浏览器，再访问 HTTPS 地址；若组织策略阻止安装，请联系终端管理员。');
    steps.appendChild(third.row); body.appendChild(steps);
    var info = el('section', 'aimcert-info'); info.appendChild(el('h3', '', '核对这张证书'));
    var list = el('dl', 'aimcert-metadata');
    list.appendChild(metadata('文件名称', CERTIFICATE.name)); list.appendChild(metadata('证书名称', CERTIFICATE.commonName));
    list.appendChild(metadata('证书主题', CERTIFICATE.subject)); list.appendChild(metadata('SHA256', CERTIFICATE.sha256, true));
    if (CERTIFICATE.notBeforeUtc && CERTIFICATE.notAfterUtc) {
      list.appendChild(metadata('生效时间', CERTIFICATE.notBeforeUtc.replace('T', ' ').replace('Z', ' UTC')));
      list.appendChild(metadata('到期时间', CERTIFICATE.notAfterUtc.replace('T', ' ').replace('Z', ' UTC')));
    }
    list.appendChild(metadata('信任位置', 'Cert:\\CurrentUser\\Root（当前 Windows 用户）'));
    info.appendChild(list); info.appendChild(el('p', 'aimcert-muted', '安装根 CA 表示信任它签发的证书。请先向服务器管理员核对来源与完整指纹。此文件仅含公钥证书，不包含私钥。'));
    info.appendChild(el('p', 'aimcert-muted', '请以完整 SHA256 区分根证书。安装脚本不会自动删除旧根证书。')); body.appendChild(info);
    var advanced = el('details', 'aimcert-alternative'); advanced.appendChild(el('summary', '', '其他安装方式与适用平台'));
    advanced.appendChild(el('h3', '', 'Windows：证书与脚本安装包'));
    advanced.appendChild(el('p', '', '将 ZIP 解压到同一文件夹，审阅 install-dispatch-certificate.ps1 后，在组织允许运行本地脚本的环境中执行。脚本只读取同目录证书，已安装时会直接跳过。若执行策略阻止 .ps1，请使用上方交互命令或联系管理员，无需修改执行策略。'));
    var downloads = el('div', 'aimcert-actions');
    downloads.appendChild(download('下载 Windows 安装包 .zip', CERTIFICATE.bundleUrl, 'dispatch-certificate-windows.zip'));
    downloads.appendChild(download('单独下载脚本 .ps1', CERTIFICATE.scriptUrl, 'install-dispatch-certificate.ps1'));
    advanced.appendChild(downloads);
    advanced.appendChild(el('h3', '', 'macOS / Linux / Firefox'));
    advanced.appendChild(el('p', '', '上方命令与脚本仅适用于 Windows。Chrome / Edge 使用 Windows 证书存储；macOS、Linux、Firefox、Safari 和 iOS 请按本组织终端策略配置，网页不会自动更改这些设置。'));
    body.appendChild(advanced); dialog.appendChild(body);
    var footer = el('div', 'aimcert-dialog-footer'); footer.appendChild(el('p', '', '帮助中心可随时再次打开本指引。')); footer.appendChild(button('知道了', '', close)); dialog.appendChild(footer);
    dialog.addEventListener('cancel', function (event) { event.preventDefault(); close(); });
    dialog.addEventListener('click', function (event) { if (event.target === dialog) { var rect=dialog.getBoundingClientRect(); if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)close(); } });
    root.document.body.appendChild(dialog); modal = dialog;
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    closeButton.focus(); return true;
  }
  function showNotice() {
    if (!owner || !verified || !windows() || hasViewed() || notice) return;
    markViewed();
    notice = el('aside', 'aimcert-notice'); notice.setAttribute('aria-label', '内网证书安装提示'); notice.setAttribute('role', 'status');
    var icon = el('span', 'aimcert-notice-icon', 'i'); icon.setAttribute('aria-hidden', 'true'); notice.appendChild(icon);
    var text = el('div', 'aimcert-notice-copy'); text.appendChild(el('strong', '', '配置此 Windows 终端的 HTTPS 证书'));
    text.appendChild(el('p', '', '请核对本页根证书指纹；已信任同一指纹时无需重复导入。本提示不代表证书已安装。'));
    var actions = el('div', 'aimcert-actions'); actions.appendChild(button('查看安装步骤', 'aimcert-button-primary', open)); actions.appendChild(button('稍后', 'aimcert-button-quiet', removeNotice)); text.appendChild(actions);
    notice.appendChild(text); root.document.body.appendChild(notice);
  }
  function open() {
    if (publicActivationPage(owner)) return Promise.resolve(false);
    if (!verification) return Promise.resolve(false);
    return verification.then(function (allowed) { return allowed ? openVerified() : false; });
  }
  function install(vm) {
    // Home also wraps these public activation routes. An auth probe there would
    // trigger the shared 401 handler and incorrectly redirect the activation flow.
    if (publicActivationPage(vm)) {
      close(); removeNotice(); owner = vm; verified = false;
      verification = Promise.resolve(false); return verification;
    }
    if (owner === vm && verification) return verification;
    close(); removeNotice(); owner = vm; verified = false;
    if (!vm || !vm.$http || typeof vm.$http.get !== 'function' || !vm.$url || !vm.$url.url_5000) {
      verification = Promise.resolve(false); return verification;
    }
    var api = String(vm.$url.url_5000).replace(/\/$/, '') + '/user_view/protected';
    verification = Promise.resolve().then(function () { return vm.$http.get(api, {withCredentials:true}); }).then(function (response) {
      if (owner !== vm || !response || Number(response.status) !== 200 || !response.data || Number(response.data.code) !== 200) return false;
      verified = true; showNotice(); return true;
    }, function () { return false; });
    if (typeof vm.$once === 'function') vm.$once('hook:beforeDestroy', function () {
      if (owner !== vm) return;
      verified = false; owner = null; verification = null; close(); removeNotice();
    });
    return verification;
  }
  root.AiMonitorCertificateHelp = {install:install, open:open};
})(window);
