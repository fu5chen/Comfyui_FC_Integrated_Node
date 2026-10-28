// FC Image Compare —— 节点内 A/B 对比（鼠标悬停跟随式分割线）
// 鼠标在图上左右移动，分割线实时跟随：线左侧显示 A、右侧显示 B。
// 预览区按图片比例自适应节点宽度，节点高度精确贴合内容（无空白）。
import { app } from "../../scripts/app.js";

app.registerExtension({
  name: "FC.CompareImages",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "FCCompareImages") return;

    // 注入样式（只注入一次）
    const styleId = "fc-compare-style";
    if (!document.getElementById(styleId)) {
      const s = document.createElement("style");
      s.id = styleId;
      s.textContent = `
.fc-compare { width: 100%; height: 260px; }
.fc-compare-wrap {
  position: relative; width: 100%; height: 100%;
  background: #141414; overflow: hidden;
  user-select: none; touch-action: none; cursor: ew-resize;
}
.fc-compare .fc-img {
  position: absolute; top: 0; left: 0;
  width: 100%; height: 100%; object-fit: contain;
}
.fc-compare .fc-divider {
  position: absolute; top: 0; bottom: 0; width: 1px; transform: translateX(-50%);
  background: rgba(255,255,255,.8); pointer-events: none; z-index: 3;
}
.fc-compare .fc-tag {
  position: absolute; top: 4px; z-index: 2;
  font-size: 10px; padding: 1px 5px; border-radius: 3px;
  background: rgba(0,0,0,.65); color: #ffd400;
}
.fc-compare .fc-tag-a { left: 4px; }
.fc-compare .fc-tag-b { right: 4px; }
.fc-compare .fc-empty {
  position: absolute; inset: 0; z-index: 1;
  display: flex; align-items: center; justify-content: center;
  color: #888; font-size: 11px; text-align: center; padding: 8px;
}`;
      document.head.appendChild(s);
    }

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const node = this;
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

      const el = document.createElement("div");
      el.className = "fc-compare";
      el.innerHTML = `
<div class="fc-compare-wrap">
  <div class="fc-empty">运行后把鼠标移到图上左右移动即可对比</div>
  <img class="fc-img fc-img-a" alt="A" draggable="false">
  <img class="fc-img fc-img-b" alt="B" draggable="false">
  <div class="fc-tag fc-tag-a">A</div>
  <div class="fc-tag fc-tag-b">B</div>
  <div class="fc-divider"></div>
</div>`;

      const wrap = el.querySelector(".fc-compare-wrap");
      const imgA = el.querySelector(".fc-img-a");
      const imgB = el.querySelector(".fc-img-b");
      const divider = el.querySelector(".fc-divider");
      const empty = el.querySelector(".fc-empty");

      const state = { pos: 0.5, aspect: 0 };
      let domWidget = null;
      let lastWidth = 0;

      // 分割线跟随
      const apply = () => {
        imgB.style.clipPath = `inset(0 0 0 ${state.pos * 100}%)`;
        divider.style.left = `${state.pos * 100}%`;
      };
      apply();

      // 高度自适应：按 图片宽高比 × 节点宽度 撑开；节点高度精确贴合内容（可增可减，无空白）
      const applyHeight = () => {
        const width = el.clientWidth || 300;
        let h = state.aspect > 0 ? Math.round(width / state.aspect) : 260;
        h = Math.max(100, Math.min(2000, h));
        el.style.height = h + "px";
        try {
          if (domWidget) domWidget.computeSize = (w) => [w, h + 6];
          const sz = node.computeSize ? node.computeSize() : null;
          if (sz && node.size) {
            if (node.size[0] < sz[0]) node.size[0] = sz[0];
            node.size[1] = sz[1]; // 精确贴合：允许缩小，消掉多余空白
          }
          if (node.graph) node.graph.setDirtyCanvas(true, false);
        } catch (_) {}
      };

      // 监听元素尺寸变化（拖动节点宽度时自动触发）
      const ro = new ResizeObserver(() => {
        const width = el.clientWidth;
        if (!width || width === lastWidth) return; // 高度变化不回环
        lastWidth = width;
        applyHeight();
      });
      ro.observe(el);

      // 图片加载后拿到真实比例，再按比例撑开
      imgA.addEventListener("load", () => {
        if (imgA.naturalWidth && imgA.naturalHeight) {
          state.aspect = imgA.naturalWidth / imgA.naturalHeight;
          applyHeight();
        }
      });

      // 鼠标悬停即跟随：不需要按住，左右移动直接看对比
      const setFromEvent = (e) => {
        const rect = wrap.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        state.pos = Math.min(1, Math.max(0, x));
        apply();
      };
      wrap.addEventListener("pointermove", setFromEvent);
      wrap.addEventListener("pointerdown", setFromEvent); // 触屏/点击同样生效
      // 双击：回到 50/50
      wrap.addEventListener("dblclick", () => { state.pos = 0.5; apply(); });

      // DOM previews sit above the canvas, so forward wheel gestures to its zoom handler.
      el.addEventListener("wheel", (event) => {
        const canvas = app.canvas?.canvas;
        if (!canvas) return;
        event.preventDefault();
        event.stopPropagation();
        canvas.dispatchEvent(new WheelEvent("wheel", {
          bubbles: true,
          cancelable: true,
          clientX: event.clientX,
          clientY: event.clientY,
          deltaX: event.deltaX,
          deltaY: event.deltaY,
          deltaZ: event.deltaZ,
          deltaMode: event.deltaMode,
          ctrlKey: event.ctrlKey,
          shiftKey: event.shiftKey,
          altKey: event.altKey,
          metaKey: event.metaKey,
        }));
      }, { passive: false, capture: true });

      domWidget = this.addDOMWidget("fc_compare", "FC_COMPARE", el, { serialize: false });
      domWidget.computeSize = (w) => [w, 266];

      const viewUrl = (info) => {
        const p = new URLSearchParams({
          filename: info?.filename ?? "",
          subfolder: info?.subfolder ?? "",
          type: info?.type ?? "temp",
        });
        return `/view?${p.toString()}`;
      };

      const onRemoved = this.onRemoved;
      this.onRemoved = function () {
        ro.disconnect();
        return onRemoved?.apply(this, arguments);
      };
      this.fcCompare = { imgA, imgB, empty, apply, tagA: el.querySelector(".fc-tag-a"), tagB: el.querySelector(".fc-tag-b") };
      this.fcCompareViewUrl = viewUrl;
      return r;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const r = onExecuted ? onExecuted.apply(this, arguments) : undefined;
      const fc = this.fcCompare;
      if (!fc || !message) return r;

      fc.tagA.textContent = message.fc_labels?.[0] ?? "A";
      fc.tagB.textContent = message.fc_labels?.[1] ?? "B";
      const a = message.fc_a?.[0];
      const b = message.fc_b?.[0];
      const bust = `&_=${Date.now()}`; // 文件名固定，加时间戳防浏览器缓存
      if (a) {
        fc.imgA.src = this.fcCompareViewUrl(a) + bust;
        fc.empty.style.display = "none";
      }
      if (b) {
        fc.imgB.src = this.fcCompareViewUrl(b) + bust;
      } else if (a) {
        fc.imgB.src = fc.imgA.src;
      }
      fc.apply();
      return r;
    };
  },
});
