
        const $ = (id) => document.getElementById(id);
        const esc = (s) => String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

        const THEMES = {
            default: {label:'商务报告', note:'用规整网格和信息卡片，清楚呈现分析与结论。'},
            modern: {label:'现代简约', note:'让留白、轻字重与细线建立阅读节奏，聚焦内容本身。'},
            creative: {label:'创意设计', note:'用几何拼贴、海报标题与错位卡片，让创意更有辨识度。'},
            luxury: {label:'竞赛提案', note:'用章节侧栏建立叙事，用独立模块展开项目论点。'},
        };

        const SAMPLE_OUTLINE = {
            title: 'AI 发展', subtitle: '从图灵测试到大模型时代',
            slides: [
                { type: 'cover', title: 'AI 发展', content: '从图灵测试到大模型时代' },
                { type: 'content', title: 'AI 发展历程', content: ['1956 达特茅斯会议，确立人工智能学科','2006 深度学习兴起，ImageNet 图像识别突破','2017 Transformer 架构问世，开启大模型时代'] },
                { type: 'content', title: 'AI 核心应用', content: ['自然语言处理：对话、翻译、写作','计算机视觉：人脸识别、自动驾驶','多模态大模型：文生图、文生视频'] },
                { type: 'final', title: '谢谢观看', content: '欢迎交流探讨' },
            ],
        };

        // 状态
        let currentTemplate = 'luxury';
        let imageMode = 'none';
        let useVision = false;
        let lastOutline = null;
        let importedOutline = null;
        // 缓存大纲来源：null=无；'imported'=来自 JSON 导入；否则为生成时的设置签名
        let lastOutlineKey = null;
        let editableOutline = null;
        let pendingOutline = null;
        let currentFilename = '';
        let currentPptxBlob = null;
        let currentPage = 0;
        let previewPage = 0;
        let workspaceOutline = SAMPLE_OUTLINE;
        let generationController = null;
        let generationKind = null;
        let generatedScenes = null;
        let generatedKey = '';
        let followGeneration = true;

        function setBusy(kind) {
            generationKind = kind;
            ['generateTool','editWorkspace','importTool','sampleTool','template','useVision','topic','useAi'].forEach(id => $(id).disabled = !!kind);
            document.querySelectorAll('#templateTabs button, input[name="imageMode"]').forEach(el => el.disabled = !!kind);
        }
        function deckKey(outline, template, mode) { return JSON.stringify([outline.slides, template, mode, outline.title]); }
        function drawGenerated() {
            const scenes = generatedScenes || [];
            currentPage = Math.max(0, Math.min(currentPage, scenes.length - 1));
            [...$('stage').querySelectorAll('.scene'), ...$('thumbList').querySelectorAll('.scene')].forEach(el => sceneObserver.unobserve(el));
            $('thumbList').innerHTML = scenes.map((scene, index) => `<button class="thumb${index===currentPage?' active':''}" data-i="${index}" aria-label="第 ${index+1} 页" aria-current="${index===currentPage}"><div class="thumb-canvas">${sceneHTML(scene)}</div><div class="thumb-label">${String(index+1).padStart(2,'0')} / ${esc(workspaceOutline.slides[scene.sourceIndex]?.title || '')}</div></button>`).join('');
            $('stage').innerHTML = scenes.length ? sceneHTML(scenes[currentPage]) : '<p class="preview-error">正在制作第一页…</p>';
            $('thumbList').querySelectorAll('button').forEach(el => el.addEventListener('click', () => { followGeneration=false; currentPage=Number(el.dataset.i); drawGenerated(); }));
            $('stage').querySelectorAll('.scene').forEach(fitScene);
            $('thumbList').querySelectorAll('.scene').forEach(fitScene);
            $('pageStatus').textContent = scenes.length ? `${currentPage+1} / ${scenes.length}` : '0 / 0';
            $('layoutStatus').textContent = generationKind === 'ppt' ? '逐页制作中' : '已生成页面';
            $('prevSlide').disabled = currentPage <= 0;
            $('nextSlide').disabled = currentPage >= scenes.length-1;
            $('nextSlide').dataset.count = scenes.length;
        }
        async function readEvents(path, payload, onEvent) {
            const controller = generationController;
            const timer = setTimeout(() => controller.abort('timeout'), 285000);
            let reader;
            try {
                const keys = getLocalKeys();
                const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json','X-DeepSeek-Key':keys.pptKey,'X-Vision-Key':keys.visionKey},body:JSON.stringify(payload),signal:controller.signal});
                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    throw new Error(data.error || `服务请求失败（${response.status}），请稍后重试`);
                }
                if (!response.body) throw new Error('当前浏览器不支持流式生成，请更新浏览器');
                reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '', result = null;
                function consume(line) {
                    if (!line.trim()) return;
                    const event = JSON.parse(line);
                    if (event.type === 'complete' || event.type === 'error') result = event;
                    onEvent(event);
                }
                while (true) {
                    const {value,done} = await reader.read();
                    buffer += decoder.decode(value, {stream:!done});
                    let boundary;
                    while ((boundary=buffer.indexOf('\n')) >= 0) { consume(buffer.slice(0,boundary)); buffer=buffer.slice(boundary+1); }
                    if (done) { consume(buffer); break; }
                }
                if (!result) throw new Error('连接提前结束，请重试；大纲已保留');
                return result;
            } catch (error) {
                if (controller.signal.aborted) throw new Error(controller.signal.reason === 'timeout' ? '生成超时，请减少页数或关闭配图后重试' : '已停止生成，可修改后重试');
                throw error;
            } finally { clearTimeout(timer); if (reader) { await reader.cancel().catch(() => {}); reader.releaseLock(); } }
        }
        function stopGeneration() { generationController?.abort(); }
        $('cancelGeneration').addEventListener('click', stopGeneration);
        $('cancelOutline').addEventListener('click', stopGeneration);
        $('topic').addEventListener('input', () => { importedOutline = null; pendingOutline = null; lastOutlineKey = null; });

        // ---------- 工具 ----------
        let toastTimer = null;
        function toast(msg) {
            const t = $('toast'); t.textContent = msg; t.classList.add('show');
            clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
        }
        function downloadJson(obj, filename) {
            const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
            URL.revokeObjectURL(url);
        }
        function setPages(v) {
            const n = Math.min(30, Math.max(1, parseInt(v, 10) || 1));
            $('pages').value = n; $('pagesRange').value = n;
        }
        function currentConfig() {
            return {
                topic: $('topic').value.trim(),
                pages: parseInt($('pages').value, 10),
                template: $('template').value,
                language: $('language').value,
                useAi: $('useAi').checked
            };
        }
        function outlineSignature(cfg) { return JSON.stringify([cfg.topic, cfg.pages, cfg.language, cfg.useAi]); }

        // ---------- 样例预览 ----------

        const sceneCache = new Map();
        const renderVersions = new WeakMap();
        function sceneHTML(scene) {
            return `<div class="slide scene" style="background:${scene.background}"><div class="scene-canvas">${scene.elements.filter(el => !scene.imageData || el.role !== 'image-placeholder').map(el => {
                const position = `left:${el.x*72}px;top:${el.y*72}px;width:${el.w*72}px;height:${el.h*72}px;`;
                return el.kind !== 'text' ? `<span class="scene-rect" style="${position}background:${el.color};border-radius:${el.kind==='ellipse'?'50%':'0'}"></span>` :
                    `<span class="scene-text" style="${position}font-family:${esc(el.font || "Microsoft YaHei")};font-size:${el.size}px;color:${el.color};font-weight:${el.bold?700:400}">${esc(el.text)}</span>`;
            }).join('')}${scene.imageData && scene.image ? `<img alt="页面配图" class="scene-image" src="${esc(scene.imageData)}" style="left:${scene.image.x*72}px;top:${scene.image.y*72}px;width:${scene.image.w*72}px;height:${scene.image.h*72}px">` : ''}</div></div>`;
        }
        async function renderDeck(thumbListEl, stageEl, slides, theme, page, onSelect, deckTitle) {
            const version = (renderVersions.get(stageEl) || 0) + 1;
            renderVersions.set(stageEl, version);
            const template = Object.keys(THEMES).find(key => THEMES[key] === theme) || 'luxury';
            const mode = imageMode;
            const title = deckTitle || slides[0]?.title || '';
            const key = JSON.stringify([slides, template, mode, title]);
            try {
                if (!sceneCache.has(key)) {
                    const response = await fetch('/api/preview', {method:'POST', headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({outline:{title, slides}, template, imageMode:mode})});
                    const result = await response.json();
                    if (!response.ok || !result.success) throw new Error(result.error || '预览失败');
                    if (sceneCache.size > 12) sceneCache.clear();
                    sceneCache.set(key, result.scenes);
                }
                if (renderVersions.get(stageEl) !== version) return;
                const scenes = sceneCache.get(key);
                page = Math.max(0, Math.min(page, scenes.length-1));
                [...stageEl.querySelectorAll('.scene'), ...thumbListEl.querySelectorAll('.scene')].forEach(el => sceneObserver.unobserve(el));
                thumbListEl.innerHTML = scenes.map((scene, i) => `<button type="button" class="thumb${i===page?' active':''}" data-i="${i}" aria-label="第 ${i+1} 页" aria-current="${i===page}"><div class="thumb-canvas">${sceneHTML(scene)}</div><div class="thumb-label">${String(i+1).padStart(2,'0')} / ${esc(slides[scene.sourceIndex]?.title || '')}</div></button>`).join('');
                stageEl.innerHTML = scenes.length ? sceneHTML(scenes[page]) : '<p>暂无页面</p>';
                thumbListEl.querySelectorAll('.thumb').forEach(el => el.addEventListener('click', () => onSelect(Number(el.dataset.i))));
                if (stageEl.id === 'stage') {
                    $('pageStatus').textContent = `${String(page+1).padStart(2,'0')} / ${String(scenes.length).padStart(2,'0')}`;
                    $('layoutStatus').textContent = ({cover:'章节封面',editorial:'编号论点',columns:'分栏布局',timeline:'时间线'})[scenes[page]?.layout] || '';
                    $('prevSlide').disabled = page <= 0;
                    $('nextSlide').disabled = page >= scenes.length-1;
                    $('nextSlide').dataset.count = scenes.length;
                }
                stageEl.querySelectorAll('.scene').forEach(fitScene);
                thumbListEl.querySelectorAll('.scene').forEach(fitScene);
            } catch (error) {
                if (renderVersions.get(stageEl) === version) stageEl.innerHTML = '<p class="preview-error">预览暂时无法加载，请稍后重试。</p>';
            }
        }
        const sceneObserver = new ResizeObserver(entries => entries.forEach(entry => {
            const canvas = entry.target.querySelector('.scene-canvas');
            if (canvas) canvas.style.transform = `scale(${entry.contentRect.width / 960})`;
        }));
        function fitScene(scene) { sceneObserver.observe(scene); }
        function renderSample() {
            if (!generationKind && generatedScenes && generatedKey !== deckKey(workspaceOutline,currentTemplate,imageMode)) $('generationProgress').hidden=true;
            const t = THEMES[currentTemplate];
            $('activeStyleLabel').textContent = t.label;
            $('styleNote').textContent = t.note;
            document.querySelectorAll('#templateTabs button').forEach(b => { b.classList.toggle('active', b.dataset.t === currentTemplate); b.setAttribute('aria-pressed', String(b.dataset.t === currentTemplate)); });
            if (generatedScenes && generatedKey === deckKey(workspaceOutline,currentTemplate,imageMode)) drawGenerated();
            else renderDeck($('thumbList'), $('stage'), workspaceOutline.slides, t, currentPage, (i) => {
                currentPage = i; renderSample();
            }, workspaceOutline.title);
            document.querySelector('.preview-header .desc').textContent = `${workspaceOutline.title} · ${workspaceOutline.slides.length} 页大纲`;
        }

        async function renderStyleLibrary() {
            await Promise.all(Object.keys(THEMES).map(async template => {
                const target = $('style-'+template);
                try {
                    const response = await fetch('/api/preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({outline:SAMPLE_OUTLINE, template, imageMode:'none'})});
                    const result = await response.json();
                    if (!response.ok || !result.success) throw new Error('preview');
                    target.innerHTML = sceneHTML(result.scenes[0]);
                    fitScene(target.querySelector('.scene'));
                } catch { target.textContent = THEMES[template].label; }
            }));
        }
        $('template').addEventListener('change', () => { currentTemplate = $('template').value; renderSample(); });
        $('editWorkspace').addEventListener('click', () => {
            editableOutline = JSON.parse(JSON.stringify(workspaceOutline));
            renderOutlineEditor(); showView('outlineView'); openModal();
        });
        renderStyleLibrary();

        $('templateTabs').addEventListener('click', (e) => {
            const btn = e.target.closest('button'); if (!btn) return;
            currentTemplate = btn.dataset.t;
            document.querySelectorAll('#templateTabs button').forEach(b => b.classList.toggle('active', b === btn));
            $('template').value = currentTemplate;
            renderSample();
        });

        // ---------- 弹窗视图 ----------
        const VIEWS = ['configView','outlineView','loadingView','resultView','errorView','imageFallbackView','settingsView'];
        function showView(name) { VIEWS.forEach(v => $(v).style.display = (v === name ? 'block' : 'none')); }
        let returnFocus = null;
        function focusDialog(id) { requestAnimationFrame(() => [...$(id).querySelectorAll('button, input, select, textarea')].find(el => !el.disabled && el.getClientRects().length)?.focus()); }
        function openModal() { returnFocus = document.activeElement; $('modal').classList.add('open'); focusDialog('modal'); }
        function closeModal() { if (generationKind === 'outline') stopGeneration(); $('modal').classList.remove('open'); returnFocus?.focus(); }

        $('generateTool').addEventListener('click', () => { showView('configView'); openModal(); });
        $('closeModal').addEventListener('click', closeModal);
        $('closeOutline').addEventListener('click', closeModal);
        $('closeImageFallback').addEventListener('click', closeModal);
        $('closeSettings').addEventListener('click', closeModal);
        $('imageFallbackBack').addEventListener('click', () => { importedOutline = pendingOutline; showView('configView'); focusDialog('modal'); });

        // ---------- 密钥设置（每人各自，存本机浏览器 localStorage） ----------
        const KEY_STORE = { ppt: 'ppt_key', vision: 'vision_key' };
        function getLocalKeys() {
            try {
                return { pptKey: localStorage.getItem(KEY_STORE.ppt) || '', visionKey: localStorage.getItem(KEY_STORE.vision) || '' };
            } catch { return { pptKey: '', visionKey: '' }; }
        }
        function maskKey(v) {
            v = v || '';
            return v.length > 8 ? `${v.slice(0,3)}****${v.slice(-4)}` : (v ? '****' : '');
        }
        function loadKeyStatus() {
            const keys = getLocalKeys();
            $('pptKeyStatus').textContent = keys.pptKey ? `已配置 · ${maskKey(keys.pptKey)}` : '未配置（AI 大纲不可用）';
            $('visionKeyStatus').textContent = keys.visionKey ? `已配置 · ${maskKey(keys.visionKey)}` : '未配置（可选，不影响生成）';
        }
        $('openSettings').addEventListener('click', () => { const k = getLocalKeys(); $('pptKeyInput').value = k.pptKey; $('visionKeyInput').value = k.visionKey; loadKeyStatus(); showView('settingsView'); });
        $('backFromSettings').addEventListener('click', () => showView('configView'));
        $('saveSettings').addEventListener('click', () => {
            const ppt = $('pptKeyInput').value.trim();
            const vision = $('visionKeyInput').value.trim();
            try {
                if (ppt) localStorage.setItem(KEY_STORE.ppt, ppt); else localStorage.removeItem(KEY_STORE.ppt);
                if (vision) localStorage.setItem(KEY_STORE.vision, vision); else localStorage.removeItem(KEY_STORE.vision);
                toast('密钥已保存到本机浏览器（仅此设备生效）');
            } catch { toast('保存失败：浏览器本地存储不可用'); return; }
            loadKeyStatus();
        });
        document.querySelectorAll('[data-image-fallback]').forEach(button => {
            button.addEventListener('click', () => {
                if (!pendingOutline || button.disabled) return;
                const radio = document.querySelector(`input[name="imageMode"][value="${button.dataset.imageFallback}"]`);
                radio.checked = true;
                radio.dispatchEvent(new Event('change'));
                doGenerate(pendingOutline);
            });
        });
        $('againBtn').addEventListener('click', () => showView('configView'));
        $('backBtn').addEventListener('click', () => showView('configView'));
        $('backToConfig').addEventListener('click', () => showView('configView'));
        $('modal').addEventListener('click', (e) => { if (e.target === $('modal')) closeModal(); });

        // ---------- 页数联动 ----------
        $('pagesRange').addEventListener('input', () => { $('pages').value = $('pagesRange').value; });
        $('pages').addEventListener('input', () => { const v = parseInt($('pages').value, 10); if (!isNaN(v)) $('pagesRange').value = Math.min(30, Math.max(1, v)); });

        // ---------- 图片方式单选 ----------
        document.querySelectorAll('input[name="imageMode"]').forEach(r => {
            r.addEventListener('change', () => {
                imageMode = document.querySelector('input[name="imageMode"]:checked').value;
                renderSample();
                document.querySelectorAll('#imageModeCards .radio-card').forEach(c => {
                    c.classList.toggle('selected', c.querySelector('input').checked);
                });
                $('realWarn').classList.toggle('show', imageMode === 'real');
                $('visionField').style.display = imageMode === 'real' ? '' : 'none';
            });
        });
        $('useVision').addEventListener('change', () => { useVision = $('useVision').checked; });

        // ---------- 导入 / 导出 ----------
        $('importTool').addEventListener('click', () => $('importFile').click());
        $('importFile').addEventListener('change', (e) => {
            const file = e.target.files[0]; if (!file) return;
            const reader = new FileReader();
            reader.onload = () => { try { handleImported(JSON.parse(reader.result)); } catch (err) { toast('导入失败：文件不是有效的 JSON'); } };
            reader.readAsText(file); e.target.value = '';
        });
        function handleImported(obj) {
            if (obj && Array.isArray(obj.slides)) {
                if (obj.title) $('topic').value = obj.title;
                importedOutline = obj;
                lastOutlineKey = 'imported';
                workspaceOutline = obj; currentPage = 0; renderSample();
                toast('已导入大纲，生成时将使用导入内容');
            } else if (obj && typeof obj.topic === 'string') {
                importedOutline = null;
                lastOutlineKey = null;
                $('topic').value = obj.topic || '';
                if (obj.pages) setPages(obj.pages);
                if (THEMES[obj.template]) { $('template').value = obj.template; currentTemplate = obj.template; renderSample(); }
                if (obj.language) $('language').value = obj.language;
                if (typeof obj.useAi === 'boolean') $('useAi').checked = obj.useAi;
                toast('已导入配置');
            } else {
                toast('导入失败：需含 slides 数组或 topic 字段');
            }
        }
        $('exportTool').addEventListener('click', () => {
            downloadJson(workspaceOutline, 'ppt_outline.json'); toast('已导出当前大纲 JSON');
        });
        $('exportOutlineBtn').addEventListener('click', () => {
            if (lastOutline) { downloadJson(lastOutline, 'ppt_outline.json'); toast('已导出大纲 JSON'); }
        });

        // ---------- 大纲编辑 ----------
        $('outlineTitle').addEventListener('input', (e) => { if (editableOutline) editableOutline.title = e.target.value; });
        $('outlineSubtitle').addEventListener('input', (e) => { if (editableOutline) editableOutline.subtitle = e.target.value; });

        function buildSlideCard(s, i) {
            const card = document.createElement('div');
            card.className = 'slide-card';
            const isContent = s.type === 'content';
            card.innerHTML = `
                <div class="slide-card-head">
                    <select class="stype">
                        <option value="cover" ${s.type==='cover'?'selected':''}>封面</option>
                        <option value="content" ${s.type==='content'?'selected':''}>内容</option>
                        <option value="final" ${s.type==='final'?'selected':''}>结束</option>
                    </select>
                    <span class="slide-idx">第 ${i+1} 页</span>
                    ${isContent ? `<select class="slayout" aria-label="页面布局">${[['auto','自动布局'],['editorial','编号论点'],['columns','分栏布局'],['timeline','时间线']].map(([value,label]) => `<option value="${value}" ${(s.layout||'auto')===value?'selected':''}>${label}</option>`).join('')}</select>` : ''}
                    <button class="del-slide" title="删除此页">×</button>
                </div>
                <input class="stitle" value="${esc(s.title||'')}" placeholder="页面标题">
                ${isContent
                    ? `<textarea class="scontent" placeholder="每行一个要点">${esc((s.content||[]).join('\n'))}</textarea>`
                    : `<input class="scontent" value="${esc(s.content||'')}" placeholder="副标题 / 说明">`}
            `;
            card.querySelector('.stype').addEventListener('change', (e) => {
                const t = e.target.value; const sl = editableOutline.slides[i];
                if (t === 'content' && !Array.isArray(sl.content)) sl.content = sl.content ? [sl.content] : [];
                if (t !== 'content' && Array.isArray(sl.content)) sl.content = sl.content.join(' / ');
                sl.type = t;
                renderOutlineEditor();
            });
            card.querySelector('.stitle').addEventListener('input', (e) => { editableOutline.slides[i].title = e.target.value; });
            card.querySelector('.slayout')?.addEventListener('change', e => { editableOutline.slides[i].layout = e.target.value; });
            const ctrl = card.querySelector('.scontent');
            ctrl.addEventListener('input', (e) => {
                const sl = editableOutline.slides[i];
                if (sl.type === 'content') sl.content = e.target.value.split('\n');
                else sl.content = e.target.value;
            });
            card.querySelector('.del-slide').addEventListener('click', () => {
                editableOutline.slides.splice(i, 1);
                renderOutlineEditor();
            });
            return card;
        }

        function renderOutlineEditor() {
            $('outlineTitle').value = editableOutline.title || '';
            $('outlineSubtitle').value = editableOutline.subtitle || '';
            const list = $('slideList');
            list.innerHTML = '';
            editableOutline.slides.forEach((s, i) => list.appendChild(buildSlideCard(s, i)));
        }

        function collectOutline() {
            const o = JSON.parse(JSON.stringify(editableOutline));
            o.title = (o.title || '').trim();
            o.subtitle = (o.subtitle || '').trim();
            o.slides = o.slides.map(s => ({
                layout: s.layout || 'auto',
                type: s.type || 'content',
                title: (s.title || '').trim(),
                content: s.type === 'content' ? (s.content || []).map(x => String(x).trim()).filter(Boolean) : String(s.content || '').trim()
            }));
            return o;
        }

        $('addSlide').addEventListener('click', () => {
            editableOutline.slides.push({ type: 'content', title: '新页面', content: ['要点 1', '要点 2', '要点 3'] });
            renderOutlineEditor();
        });

        // ---------- 生成流程 ----------
        $('doGenerate').addEventListener('click', async () => {
            if (generationKind) return;
            const cfg = currentConfig();
            const sig = outlineSignature(cfg);
            if (importedOutline && (lastOutlineKey === sig || lastOutlineKey === 'imported')) {
                editableOutline = JSON.parse(JSON.stringify(importedOutline));
                renderOutlineEditor(); showView('outlineView'); return;
            }
            if (!cfg.topic) { toast('请输入 PPT 主题，或先导入大纲'); $('topic').focus(); return; }

            $('doGenerate').disabled = true;
            pendingOutline = null;
            generationController = new AbortController();
            setBusy('outline');
            $('outlineProgressList').replaceChildren();
            [...$('outlineProgressSteps').children].forEach((el,i) => el.classList.toggle('active', i===0));
            $('loadingTitle').textContent = '正在生成大纲';
            $('loadingDesc').textContent = 'AI 正在构思内容，请稍候…';
            showView('loadingView');

            try {
                const data = await readEvents('/api/outline/stream', cfg, event => {
                    if (event.type === 'stage') $('loadingDesc').textContent = event.message;
                    if (event.type === 'outline_slide') {
                        [...$('outlineProgressSteps').children].forEach((el,i) => el.classList.toggle('active', i<=1));
                        const card = document.createElement('article'); card.className='outline-progress-card';
                        const heading = document.createElement('strong'); heading.textContent=`${event.index+1}. ${event.slide.title || '页面'}`;
                        const content = document.createElement('p'); content.textContent=Array.isArray(event.slide.content)?event.slide.content.join('\n'):String(event.slide.content||'');
                        card.append(heading,content); $('outlineProgressList').append(card);
                    }
                });
                if (data.success && data.outline && data.outline.slides) {
                    [...$('outlineProgressSteps').children].forEach(el => el.classList.add('active'));
                    editableOutline = data.outline;
                    importedOutline = data.outline;
                    lastOutlineKey = sig;
                    renderOutlineEditor();
                    showView('outlineView');
                    if (data.mode === 'template') toast('已生成占位大纲；内容约束需启用 AI 才能应用');
                } else {
                    $('mErrorText').textContent = data.error || '大纲生成失败';
                    showView('errorView');
                }
            } catch (err) {
                $('mErrorText').textContent = err.message;
                showView(generationController?.signal.aborted && generationController.signal.reason !== 'timeout' ? 'configView' : 'errorView');
            } finally {
                $('doGenerate').disabled = false;
                setBusy(null); generationController = null;
                focusDialog('modal');
            }
        });

        $('confirmGenerate').addEventListener('click', () => {
            const outline = collectOutline();
            if (!outline.slides || outline.slides.length === 0) { toast('至少需要一页内容'); return; }
            pendingOutline = outline;
            doGenerate(outline);
        });

        async function doGenerate(outline) {
            if (generationKind) return;
            pendingOutline = outline;
            const cfg = currentConfig();
            generationController = new AbortController(); setBusy('ppt');
            workspaceOutline = outline; importedOutline = outline; currentTemplate = cfg.template;
            currentPage = 0; followGeneration = true;
            generatedScenes = []; generatedKey = deckKey(outline,cfg.template,imageMode);
            renderVersions.set($('stage'), (renderVersions.get($('stage')) || 0) + 1);
            currentPptxBlob = null; currentFilename = '';
            $('generationProgress').hidden=false; $('workspaceDownload').hidden=true; $('cancelGeneration').hidden=false;
            $('deckProgress').value=0; $('generationMessage').textContent='正在准备制作';
            closeModal(); renderSample(); $('cancelGeneration').focus();
            $('confirmGenerate').disabled = true;
            document.querySelectorAll('[data-image-fallback]').forEach(button => button.disabled = true);

            try {
                const data = await readEvents('/api/generate/stream', {template:cfg.template,imageMode,useVision,outline}, event => {
                    if (event.type === 'stage') $('generationMessage').textContent=event.message;
                    if (event.type === 'slide') {
                        generatedScenes[event.index]=event.scene;
                        if (followGeneration) currentPage=event.index;
                        $('deckProgress').value=Math.round((event.index+1)/event.total*95);
                        $('generationMessage').textContent=`已完成 ${event.index+1} / ${event.total} 页${event.index+1===event.total?'，正在打包 PPTX':''}`;
                        drawGenerated();
                    }
                });
                if (data.code === 'IMAGE_SEARCH_FAILED') {
                    pendingOutline = data.outline || outline;
                    importedOutline = pendingOutline;
                    const failedSlide = pendingOutline.slides[data.sourceIndex];
                    $('imageFallbackMessage').textContent = `“${failedSlide?.title || '当前页面'}”未能取得可用图片，可能是网络异常、没有搜索结果或图片下载失败。请选择一种方式继续。`;
                    showView('imageFallbackView');
                    openModal();
                    $('generationMessage').textContent='配图失败，等待选择后继续';
                } else if (data.success) {
                    lastOutline = data.outline || outline;
                    workspaceOutline = lastOutline;
                    currentPage = 0;
                    currentTemplate = cfg.template;
                    document.querySelectorAll('#templateTabs button').forEach(button => button.classList.toggle('active', button.dataset.t === currentTemplate));
                    currentFilename = data.filename;
                    currentPptxBlob = data.file ? b64ToBlob(data.file, 'application/vnd.openxmlformats-officedocument.presentationml.presentation') : null;
                    $('mFilename').textContent = data.filename;
                    $('previewFilename').textContent = data.filename;
                    $('deckProgress').value=100;
                    $('generationMessage').textContent=`制作完成 · ${generatedScenes.length} 页，PPTX 已就绪`;
                    $('workspaceDownload').hidden=false;
                    $('workspaceDownload').focus();
                } else {
                    $('mErrorText').textContent = data.error || '未知错误';
                    showView('errorView');
                    openModal(); $('generationMessage').textContent='制作未完成，可重试';
                }
            } catch (err) {
                $('mErrorText').textContent = err.message;
                showView('errorView');
                openModal(); $('generationMessage').textContent=err.message;
            } finally {
                $('confirmGenerate').disabled = false;
                document.querySelectorAll('[data-image-fallback]').forEach(button => button.disabled = false);
                setBusy(null); generationController=null;
                $('cancelGeneration').hidden=true;
                renderSample();
            }
        }

        $('retryBtn').addEventListener('click', () => { if (pendingOutline) doGenerate(pendingOutline); else $('doGenerate').click(); });

        // ---------- 下载 PPTX ----------
        function b64ToBlob(b64, mime) {
            const bin = atob(b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            return new Blob([bytes], { type: mime });
        }
        function downloadPptx() {
            if (!currentPptxBlob) { toast('请先生成 PPT'); return; }
            const url = URL.createObjectURL(currentPptxBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = currentFilename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
        $('downloadBtn').addEventListener('click', downloadPptx);
        $('workspaceDownload').addEventListener('click', downloadPptx);

        // ---------- 预览弹窗 ----------
        function renderPreview(outline, t) {
            const slides = (outline && outline.slides) ? outline.slides : [];
            previewPage = 0;
            const draw = () => renderDeck($('previewThumbList'), $('previewStage'), slides, t, previewPage, (i) => {
                previewPage = i; draw();
            }, outline.title);
            draw();
        }
        function openPreviewModal() { returnFocus = document.activeElement; $('previewModal').classList.add('open'); focusDialog('previewModal'); }
        function closePreviewModal() { $('previewModal').classList.remove('open'); returnFocus?.focus(); }
        $('previewClose').addEventListener('click', closePreviewModal);
        $('previewDownloadBtn').addEventListener('click', downloadPptx);
        $('previewOutlineBtn').addEventListener('click', () => {
            if (lastOutline) { downloadJson(lastOutline, 'ppt_outline.json'); toast('已导出大纲 JSON'); }
        });
        $('previewAgainBtn').addEventListener('click', () => { closePreviewModal(); showView('configView'); openModal(); });
        $('previewModal').addEventListener('click', (e) => { if (e.target === $('previewModal')) closePreviewModal(); });

        // ---------- 示例 / 待定 ----------
        $('sampleTool').addEventListener('click', () => { workspaceOutline = SAMPLE_OUTLINE; importedOutline = null; lastOutlineKey = null; currentPage = 0; renderSample(); toast('已还原示例预览'); });

        // ---------- 弹窗细化：字数统计 / 模板说明 / 帮助提示 ----------
        function updateTopicCount() {
            const c = $('topicCount');
            if (c) c.textContent = `${$('topic').value.length} / 200`;
        }
        $('topic').addEventListener('input', updateTopicCount);
        updateTopicCount();

        $('template').addEventListener('change', () => {
            const t = THEMES[$('template').value];
            if ($('templateDesc') && t) $('templateDesc').textContent = t.note;
        });

        const helpToggle = $('topicHelpToggle'), helpTip = $('topicHelpTip');
        if (helpToggle && helpTip) {
            helpToggle.addEventListener('click', () => {
                const open = helpTip.hidden;
                helpTip.hidden = !open;
                helpToggle.setAttribute('aria-expanded', String(open));
            });
        }
        
        

        renderSample();
    
        $('prevSlide').addEventListener('click', () => { followGeneration=false; currentPage = Math.max(0,currentPage-1); renderSample(); });
        $('nextSlide').addEventListener('click', () => { followGeneration=false; currentPage = Math.min(Number($('nextSlide').dataset.count)-1,currentPage+1); renderSample(); });
        $('presentTool').addEventListener('click', async () => {
            try { if (document.fullscreenElement) await document.exitFullscreen(); else await $('stage').requestFullscreen(); }
            catch { toast('当前浏览器不支持全屏'); }
        });
        document.addEventListener('keydown', event => {
            const modal = document.querySelector('.modal-overlay.open');
            if (event.key === 'Tab' && modal) {
                const focusable = [...modal.querySelectorAll('button, input, select, textarea, [tabindex="0"]')].filter(el => !el.disabled && el.getClientRects().length);
                const first = focusable[0], last = focusable[focusable.length-1];
                if (event.shiftKey && (document.activeElement===first || !modal.contains(document.activeElement))) { event.preventDefault(); last?.focus(); }
                else if (!event.shiftKey && (document.activeElement===last || !modal.contains(document.activeElement))) { event.preventDefault(); first?.focus(); }
            }
            if (event.key === 'Escape') { closeModal(); closePreviewModal(); }
            if (/INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || document.querySelector('.modal-overlay.open')) return;
            if (event.key === 'ArrowRight') $('nextSlide').click();
            if (event.key === 'ArrowLeft') $('prevSlide').click();
        });
