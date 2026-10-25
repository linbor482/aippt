# Studio.css 颜色映射到 Tokens.css

## tokens.css 可用变量

```css
--c-bg:            #f1f0ea   /* 工作区底色 */
--c-surface:       #fffdf8   /* 顶栏/侧栏/弹窗 */
--c-surface-2:     #f8f7f2   /* 卡内浅底 */
--c-surface-3:     #efeee7   /* 凹陷/轨道 */
--c-canvas:        #e9e8e1   /* 舞台衬底 */

--c-line:          #e4e6de
--c-line-strong:   #d2d6ca
--c-line-faint:    #eef0e9

--c-text:          #1f2c24
--c-text-2:        #4d5a50
--c-muted:         #7d867a
--c-faint:         #9ca396

--c-accent:        #2e4938   /* 主色：按钮/选中 */
--c-accent-hi:     #3d5f49   /* 主色 hover */
--c-accent-soft:   #edf2e5   /* 主色淡底 */
--c-accent-line:   #7c9764   /* 主色描边 */
--c-accent-glow:   rgba(46, 73, 56, .18)

--c-ok:            #6b8b4c
```

## 映射表（优先级高的替换）

### 背景色系
- `#fffefa` (8次) → `var(--c-surface)` (原:#fffdf8，接近)
- `#f4f3ef` → `var(--c-bg)` (原:#f1f0ea)
- `#f6f8f5` → `var(--c-surface-2)` (原:#f8f7f2)
- `#fff` (9次) → 保留（纯白，语义明确）

### 边框/线条
- `#dce2dd` (2次) → `var(--c-line)` (原:#e4e6de，接近)
- `#e4e6dd` → `var(--c-line)`
- `#e1e4dd` → `var(--c-line)`

### 文字色
- `#27362e` → `var(--c-text)` (原:#1f2c24，需调整 tokens)
- `#222823` → `var(--c-text)`
- `#727c74` (2次) → `var(--c-muted)` (原:#7d867a)
- `#7a8179` → `var(--c-muted)`

### 主色（绿色）
- `#27735b` (3次) → `var(--c-accent)` ⚠️ 需更新 tokens（原:#2e4938 太暗）
- `#263d2d` (3次) → `var(--c-accent)` 
- `#7c9764` (2次) → `var(--c-accent-line)`
- `#6b8b4c` → `var(--c-ok)`

### 策略
1. 先更新 tokens.css 的主色值，使其与 studio.css 第一版设计一致
2. 再批量替换 studio.css 中的硬编码值
3. 保留纯白 #fff 和纯黑 #111（语义明确）
4. 保留半透明色（如 #6e8b551a）暂不处理
