/* 分类页面前端：只调 /api，不包含仿真计算 */
const BLOCKED = "思考遇到一些阻碍，请稍后再试。";
let overview = null;

function $(id) { return document.getElementById(id); }

function toast(text) {
  const box = $("toast");
  box.textContent = text || BLOCKED;
  box.style.display = "block";
  setTimeout(() => { box.style.display = "none"; }, 2600);
}

async function api(url, options) {
  try {
    const res = await fetch(url, options);
    const data = await res.json();
    if (data && data.ok === false && data.message) toast(data.message);
    return data;
  } catch (err) {
    toast(BLOCKED);
    return { ok: false, message: BLOCKED };
  }
}

function postJson(url, body) {
  return api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

function levelClass(level) {
  if (level === "ok" || level === "success") return "ok";
  if (level === "warn" || level === "warning") return "warn";
  if (level === "danger" || level === "error") return "bad";
  return "";
}

function renderTable(rows) {
  if (!rows || !rows.length) return "<p class='hint'>暂无记录。</p>";
  const keys = Object.keys(rows[0]);
  const head = keys.map((k) => "<th>" + k + "</th>").join("");
  const body = rows.map((row) => "<tr>" + keys.map((k) => "<td>" + (row[k] ?? "") + "</td>").join("") + "</tr>").join("");
  return "<table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table>";
}

function renderChat(chat) {
  const box = $("chat-box");
  box.innerHTML = "";
  (chat || []).forEach((msg) => {
    const div = document.createElement("div");
    div.className = "msg " + (msg.role === "user" ? "user" : "assistant");
    div.textContent = (msg.role === "user" ? "你：" : "系统：") + (msg.content || "");
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

function renderDiagnosis(diag) {
  const box = $("diagnosis");
  if (!diag || !diag.lines || !diag.lines.length) {
    box.textContent = "还没有执行过指令。发送一句后，这里会告诉你成功或失败原因。";
    box.className = "";
    return;
  }
  box.className = levelClass(diag.level);
  box.textContent = diag.lines.join("\n");
}

function renderState(state, physics) {
  const s = state || {};
  $("step-t").textContent = String(s.t || 0);
  $("state-box").textContent = JSON.stringify({
    joint_positions: s.joint_positions || [],
    model_ref: s.model_ref || "",
    flow: s.flow || {},
  }, null, 2);
  const joints = s.joint_positions && s.joint_positions.length ? s.joint_positions : [0, 0];
  const host = $("joints");
  if (host.childElementCount !== joints.length) {
    host.innerHTML = "";
    const p = physics || {};
    const min = Number(p.joint_range_min ?? -2.8);
    const max = Number(p.joint_range_max ?? 2.8);
    joints.forEach((val, i) => {
      const wrap = document.createElement("div");
      wrap.innerHTML = "<label>关节 " + (i + 1) + " <span id='jv" + i + "'></span></label><input type='range' id='joint" + i + "' min='" + min + "' max='" + max + "' step='0.05'>";
      host.appendChild(wrap);
    });
  }
  joints.forEach((val, i) => {
    const input = $("joint" + i);
    const label = $("jv" + i);
    if (!input) return;
    if (document.activeElement !== input) input.value = Number(val).toFixed(2);
    if (label) label.textContent = Number(input.value).toFixed(2);
    input.oninput = () => { if (label) label.textContent = Number(input.value).toFixed(2); };
  });
}

function fillPhysics(physics) {
  const p = physics || {};
  const map = [
    ["friction", "v-friction", p.friction ?? 1],
    ["damping", "v-damping", p.joint_damping ?? 0.5],
    ["rmin", "v-rmin", p.joint_range_min ?? -2.8],
    ["rmax", "v-rmax", p.joint_range_max ?? 2.8],
  ];
  map.forEach(([id, vid, val]) => {
    const input = $(id);
    if (document.activeElement !== input) input.value = val;
    $(vid).textContent = Number(input.value).toFixed(2);
    input.oninput = () => { $(vid).textContent = Number(input.value).toFixed(2); };
  });
}

function applyOverview(data) {
  overview = data;
  $("title").textContent = data.title || "RobeWhisper机器人自然语言编程平台";
  $("caption").textContent = data.caption || "";
  $("hint").textContent = data.hint || "";
  const banner = data.banner || {};
  const lines = [banner.title || ""].concat(banner.lines || []).filter(Boolean);
  $("banner").textContent = lines.join("\n");
  $("banner").className = "banner " + (banner.level || "");
  $("chat-meta").textContent = "解析：" + (data.llm_backend || "mock") + " ｜ 实际：" + (data.llm_effective || "") + " ｜ 机器人：" + (data.robot_backend || "") + " ｜ 真机发送：" + (data.use_real_robot ? "已开" : "关") + " ｜ 策略：" + (data.rsr_policy || "");
  $("rsr").checked = !!data.rsr_enable;
  $("rsr-line").textContent = data.rsr_line || "";
  $("rsr-line").className = "meta " + levelClass(data.rsr_level);
  renderChat(data.chat || []);
  renderDiagnosis(data.diagnosis);
  $("proxy").textContent = (data.proxy && data.proxy.length) ? data.proxy.join("\n") : "还没跑过指令。";
  const rsr = data.rsr || {};
  if (!rsr.enabled && !rsr.has_result) {
    $("rsr-box").textContent = "当前关着：不会做校准。需要时再勾选开关。";
  } else if (!rsr.has_result) {
    $("rsr-box").textContent = "已勾选校准，但还没有成功跑过带校准的指令。";
  } else {
    $("rsr-box").textContent = "对照来源：" + rsr.source_label + " ｜ MAE：" + rsr.mae + " ｜ 参数已更新：" + (rsr.updated ? "是" : "否") + " ｜ 帧数：" + rsr.frames + "\n" + (rsr.message || "");
  }
  const select = $("model-select");
  const models = data.models || [];
  select.innerHTML = models.map((m) => "<option value='" + m.ref + "'>" + m.label + "</option>").join("");
  select.value = data.model_ref || "default";
  fillPhysics(data.physics);
  renderState(data.state, data.physics);
  $("ready-line").textContent = data.ready ? "系统就绪：可以输入自然语言做虚拟试机。" : "系统未完全就绪，请先看下方需注意。";
  $("ready-line").className = data.ready ? "ok" : "bad";
  $("catalog").innerHTML = (data.catalog || []).map((item) => "<p><strong>" + item.title + "</strong><br>是什么：" + item.what + "<br>" + item.default + "<br>怎么开：" + item.how + "</p>").join("");
  $("switches").innerHTML = (data.switches || []).map((row) => "<p class='" + levelClass(row.level) + "'>" + row.title + "：" + row.label + " — " + row.reason + "</p>").join("");
  $("ok-items").innerHTML = (data.ok_items || []).map((x) => "<p class='ok'>" + x + "</p>").join("") || "<p class='hint'>暂无</p>";
  $("issues").innerHTML = (data.issues || []).map((x) => "<p class='warn'>" + x + "</p>").join("") || "<p class='hint'>暂无</p>";
  $("cap-md").textContent = data.capabilities_md || "";
  const contact = data.contact || {};
  $("contact-line").textContent = (contact.label || "") + " — " + (contact.detail || "");
  $("contact-line").className = levelClass(contact.level);
  const samples = $("samples");
  samples.innerHTML = "";
  (data.samples || []).forEach((sample) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = sample.label;
    btn.title = sample.hint || "";
    btn.onclick = () => sendText(sample.text);
    samples.appendChild(btn);
  });
}

async function refresh() {
  const data = await api("/api/overview");
  if (data && data.title) applyOverview(data);
}

async function sendText(text) {
  const data = await postJson("/api/instruction", { text: text });
  if (data && data.chat) {
    renderChat(data.chat);
    renderDiagnosis(data.diagnosis);
    if (data.proxy) $("proxy").textContent = data.proxy.length ? data.proxy.join("\n") : "还没跑过指令。";
    if (data.state) renderState(data.state, overview && overview.physics);
  }
  await refresh();
}

document.querySelectorAll("nav button").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "data") loadRecords();
  };
});

$("send").onclick = () => {
  const text = $("prompt").value.trim();
  if (!text) { toast("请先输入一句指令，或点一个样例。"); return; }
  $("prompt").value = "";
  sendText(text);
};
$("clear-chat").onclick = async () => { await postJson("/api/chat/clear", {}); await refresh(); };
$("rsr").onchange = async () => { await postJson("/api/rsr", { enabled: $("rsr").checked }); await refresh(); };
$("load-model").onclick = async () => { const r = await postJson("/api/models/load", { ref: $("model-select").value }); if (r.message) toast(r.message); await refresh(); };
$("load-default").onclick = async () => { const r = await postJson("/api/models/load", { ref: "default" }); if (r.message) toast(r.message); await refresh(); };
$("upload-model").onclick = async () => {
  const file = $("model-file").files[0];
  if (!file) { toast("请先选择 .xml 或 .mjcf 文件。"); return; }
  const form = new FormData();
  form.append("file", file);
  const r = await api("/api/models/upload", { method: "POST", body: form });
  if (r.message) toast(r.message);
  await refresh();
};
$("apply-physics").onclick = async () => {
  const r = await postJson("/api/physics", {
    friction: Number($("friction").value),
    joint_damping: Number($("damping").value),
    joint_range_min: Number($("rmin").value),
    joint_range_max: Number($("rmax").value),
  });
  if (r.message) toast(r.message);
  await refresh();
};
$("do-step").onclick = async () => {
  const targets = [];
  let i = 0;
  while ($("joint" + i)) { targets.push(Number($("joint" + i).value)); i += 1; }
  const r = await postJson("/api/step", { joint_targets: targets });
  if (r.message) toast(r.message);
  if (r.state) renderState(r.state, overview && overview.physics);
  await refresh();
};
$("do-reset").onclick = async () => { const r = await postJson("/api/reset", {}); if (r.message) toast(r.message); await refresh(); };
$("do-reload").onclick = async () => { const r = await postJson("/api/reload", {}); if (r.message) toast(r.message); await refresh(); };
$("probe-http").onclick = async () => { const r = await postJson("/api/probe/http", {}); $("probe-box").textContent = r.message || BLOCKED; };
$("probe-llm").onclick = async () => { const r = await postJson("/api/probe/llm", {}); $("probe-box").textContent = r.message || BLOCKED; };
$("contact-on").onclick = async () => {
  const loaded = await postJson("/api/models/load", { ref: "builtin_arm2_contact" });
  if (loaded.message) toast(loaded.message);
  if (loaded.ok) await sendText("抓起红色积木");
  else await refresh();
};
$("contact-off").onclick = async () => { const r = await postJson("/api/models/load", { ref: "default" }); if (r.message) toast(r.message); await refresh(); };
$("overlimit").onclick = async () => { await postJson("/api/demo/overlimit", {}); await refresh(); };

async function loadRecords() {
  const data = await api("/api/records");
  $("exp-table").innerHTML = renderTable(data.experiments);
  $("mem-table").innerHTML = renderTable(data.experiences);
}

async function exportPack(latest) {
  const r = await postJson("/api/demo-pack", { experiment_id: latest ? "" : $("pack-id").value.trim(), latest: latest });
  $("pack-msg").textContent = r.message || "";
  if (r.ok && r.download_name) {
    const a = document.createElement("a");
    a.href = "/api/demo-pack/download?name=" + encodeURIComponent(r.download_name);
    a.textContent = "下载演示包 " + r.download_name;
    $("pack-msg").appendChild(document.createElement("br"));
    $("pack-msg").appendChild(a);
  }
}
$("pack-latest").onclick = () => exportPack(true);
$("pack-id-btn").onclick = () => exportPack(false);

refresh();