import { app } from "../../scripts/app.js";

app.registerExtension({
  name: "FC.LoadModel.LoRAStack",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "FCLoadModel") return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = created?.apply(this, arguments);
      const find = (name) => this.widgets.find((w) => w.name === name);
      const storage = find("lora_stack");
      const legacy = ["lora_name", "strength_model", "strength_clip"].map(find);
      const master = find("lora_enabled");
      for (const w of [...legacy, storage, master]) {
        w.type = "fc_hidden";
        w.computeSize = () => [0, -4];
      }
      master.value = true;
      const container = document.createElement("div");
      container.className = "fc-lora-stack";
      container.style.cssText = "width:100%;display:flex;flex-direction:column;gap:4px;font:12px Arial;color:#ddd;box-sizing:border-box;padding:2px 0;";
      // The hidden JSON is the only serialized state; the compact UI has no workflow inputs.
      const panel = this.addDOMWidget("fc_lora_panel", "FC_LORA_PANEL", container, { serialize: false });
      let rows = [];
      const sync = () => {
        master.value = true;
        storage.value = JSON.stringify(rows);
        this.setDirtyCanvas(true, true);
      };
      const controlStyle = "background:#282828;color:#ddd;border:1px solid #555;border-radius:5px;height:26px;box-sizing:border-box;font:12px Arial;";
      const render = () => {
        container.replaceChildren();
        rows.forEach((row, i) => {
          const line = document.createElement("div");
          line.style.cssText = "display:flex;align-items:center;gap:4px;height:28px;flex-shrink:0;";
          const select = document.createElement("select");
          select.title = `LoRA ${i + 1}（None = 不应用）`;
          select.style.cssText = controlStyle + "flex:1;min-width:0;padding:0 5px;text-overflow:ellipsis;";
          const names = [...nodeData.input.required.lora_name[0]];
          if (!names.includes(row.name)) names.push(row.name);
          for (const name of names) {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            select.appendChild(option);
          }
          select.value = row.name;
          select.addEventListener("change", () => { row.name = select.value; sync(); });
          line.appendChild(select);
          for (const [key, short, title] of [["strength_model", "M", "LoRA 模型强度"], ["strength_clip", "C", "CLIP 强度"]]) {
            const label = document.createElement("label");
            label.title = title;
            label.style.cssText = "display:flex;align-items:center;gap:3px;flex-shrink:0;";
            const text = document.createElement("span");
            text.textContent = short;
            text.style.color = "#999";
            const input = document.createElement("input");
            input.type = "number";
            input.min = -100;
            input.max = 100;
            input.step = 0.01;
            input.value = row[key];
            input.title = title;
            input.style.cssText = controlStyle + "width:60px;padding:0 3px;text-align:center;";
            input.addEventListener("change", () => {
              const value = Number(input.value);
              if (input.value.trim() && Number.isFinite(value)) {
                row[key] = Math.max(-100, Math.min(100, value));
                sync();
              }
              input.value = row[key];
            });
            label.append(text, input);
            line.appendChild(label);
          }
          container.appendChild(line);
        });
        const bar = document.createElement("div");
        bar.style.cssText = "display:flex;height:28px;flex-shrink:0;border:1px solid #555;border-radius:6px;overflow:hidden;";
        for (const [text, title, action] of [
          ["−", "减少一个 LoRA（移除最后一项）", () => rows.pop()],
          ["+", "增加一个 LoRA", () => { if (rows.length < 64) rows.push({ name: "None", strength_model: 1, strength_clip: 1 }); }],
        ]) {
          const button = document.createElement("button");
          button.textContent = text;
          button.title = title;
          button.style.cssText = "flex:1;background:#282828;color:#ddd;border:0;font:18px Arial;cursor:pointer;";
          if (text === "+") button.style.borderLeft = "1px solid #555";
          button.disabled = text === "−" ? rows.length === 0 : rows.length >= 64;
          button.addEventListener("click", () => { action(); sync(); render(); });
          bar.appendChild(button);
        }
        container.appendChild(bar);
        const height = rows.length * 32 + 34;
        container.style.height = `${height}px`;
        panel.computeSize = (width) => [width, height];
        this.setSize([Math.max(this.size[0], 420), this.computeSize()[1]]);
        this.setDirtyCanvas(true, true);
      };
      const restore = () => {
        if (storage.value) {
          try { rows = JSON.parse(storage.value); }
          catch (error) { console.error("FC Load model: invalid LoRA stack", error); return; }
          if (!Array.isArray(rows)) return;
        } else {
          rows = [{ name: legacy[0].value || "None",
            strength_model: legacy[1].value ?? 1, strength_clip: legacy[2].value ?? 1 }];
        }
        rows = rows.map((row) => ({ name: row.name || "None",
          strength_model: row.strength_model ?? 1, strength_clip: row.strength_clip ?? 1 }));
        sync(); render();
      };
      const configured = this.onConfigure;
      this.onConfigure = function () {
        const value = configured?.apply(this, arguments);
        if ((arguments[0]?.widgets_values?.length ?? 0) < 9) storage.value = "";
        restore();
        return value;
      };
      restore();
      return result;
    };
  },
});
