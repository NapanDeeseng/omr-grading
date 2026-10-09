// กล้องสแกนกระดาษแบบเต็มจอ — st.components.v2 (ฝั่ง Python อยู่ใน camera.py)
// เปิดกล้องหลังทันทีพร้อมกรอบเล็งแบบตอนสแกน QR จ่ายเงิน ถ่ายแล้วส่งภาพ JPEG (data URL) กลับเป็น trigger "photo"
// เปิดกล้องในเบราว์เซอร์ไม่ได้ (ไม่ให้สิทธิ์ / http / ไม่มีกล้อง) → ใช้แอปกล้องของเครื่องผ่าน <input capture> แทน

const MAX_SIDE = 3000; // ด้านยาวสุดของภาพที่ส่งกลับ — พออ่านวงฝนได้ชัด และไม่ทำให้ส่งขึ้นเซิร์ฟเวอร์ช้า
const JPEG_QUALITY = 0.92;
const COOLDOWN_MS = 900; // กันกดรัวจนภาพก่อนหน้ายังส่งไม่ถึง Python

const ICONS = {
  camera: '<path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.6l1.4-2h5l1.4 2h1.6A2.5 2.5 0 0 1 20 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5z"/><circle cx="12" cy="12.8" r="3.6"/>',
  phone: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><circle cx="12" cy="9.5" r="2.4"/><path d="M10.5 18h3"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  torch: '<path d="M8 3h8l-1.5 6h-5zM9.5 9h5v10.5a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2zM12 13v2.5"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.2 2.4 2.4 4.6-4.8"/>',
  off: '<path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.6l1.4-2h5l1.4 2h1.6A2.5 2.5 0 0 1 20 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5z"/><path d="m3 3 18 18"/>',
};
const svg = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;

// จำว่าเปิดกล้องอัตโนมัติไปแล้วสำหรับรอบที่เลือกโหมดกล้อง (open_token) — rerun/เปลี่ยนหน้ากลับมาจะไม่เด้งกล้องซ้ำ
const opened = (window.__omrScanOpened ??= {});

function cameraError(err) {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
    return "เบราว์เซอร์นี้เปิดกล้องในหน้าเว็บไม่ได้ (ต้องเปิดผ่าน https://) ใช้แอปกล้องของเครื่องแทนได้";
  switch (err?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "ยังไม่ได้อนุญาตให้ใช้กล้อง — เปิดสิทธิ์กล้องให้เว็บนี้ในการตั้งค่าเบราว์เซอร์ หรือใช้แอปกล้องของเครื่องแทน";
    case "NotFoundError":
    case "OverconstrainedError":
      return "ไม่พบกล้องบนอุปกรณ์นี้";
    case "NotReadableError":
      return "กล้องถูกแอปอื่นใช้อยู่ — ปิดแอปนั้นแล้วลองใหม่";
    default:
      return "เปิดกล้องไม่สำเร็จ ลองใหม่อีกครั้ง หรือใช้แอปกล้องของเครื่องแทน";
  }
}

/** ย่อภาพ (video / ImageBitmap) ให้ด้านยาวไม่เกิน MAX_SIDE แล้วคืน data URL ของ JPEG */
function toJpeg(source, width, height) {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", JPEG_QUALITY);
}

async function fileToJpeg(file) {
  // createImageBitmap หมุนภาพตาม EXIF ให้แล้ว (ภาพจากแอปกล้องมือถือมักเก็บแนวนอน + ป้ายหมุน)
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    return toJpeg(bmp, bmp.width, bmp.height);
  } finally {
    bmp.close?.();
  }
}

class Scanner {
  constructor(opts, { onShot, onNative }) {
    this.opts = opts;
    this.onShot = onShot;
    this.onNative = onNative;
    this.stream = null;
    this.count = 0;
    this.host = null;
  }

  get isOpen() {
    return this.host !== null;
  }

  open() {
    if (this.isOpen) return;
    const { css, title, hint, multiple } = this.opts;
    this.host = document.createElement("div");
    this.host.dataset.omrScanner = "";
    const root = this.host.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${css}</style>
      <div class="scan" role="dialog" aria-modal="true" aria-label="${title}">
        <video playsinline muted autoplay></video>
        <header class="top">
          <button class="icon-btn close" type="button" aria-label="ปิดกล้อง">${svg("close")}</button>
          <div class="title">${title}</div>
          <button class="icon-btn torch ghost" type="button" aria-label="ไฟฉาย" aria-pressed="false">${svg("torch")}</button>
        </header>
        <div class="stage">
          <div class="frame">
            <i class="c tl"></i><i class="c tr"></i><i class="c bl"></i><i class="c br"></i>
            <i class="m tl"></i><i class="m tr"></i><i class="m bl"></i><i class="m br"></i>
            <div class="line"></div>
          </div>
          <p class="hint">${hint}</p>
        </div>
        <footer class="bottom">
          <div class="thumb" hidden><img alt=""><span class="count">0</span></div>
          <button class="shutter" type="button" aria-label="ถ่ายภาพ" disabled><span></span></button>
          <button class="done" type="button" ${multiple ? "" : "hidden"} disabled>เสร็จ</button>
        </footer>
        <div class="flash"></div>
        <div class="toast" role="status" aria-live="polite"></div>
        <div class="state loading"><div class="spinner"></div></div>
      </div>`;
    document.body.appendChild(this.host);
    this.prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // กันหน้าเว็บข้างหลังเลื่อนตามนิ้ว

    const $ = (sel) => root.querySelector(sel);
    this.el = {
      video: $("video"), shutter: $(".shutter"), done: $(".done"), torch: $(".torch"), thumb: $(".thumb"),
      thumbImg: $(".thumb img"), count: $(".count"), flash: $(".flash"), toast: $(".toast"), state: $(".state"),
    };
    $(".close").addEventListener("click", () => this.close());
    this.el.done.addEventListener("click", () => this.close());
    this.el.shutter.addEventListener("click", () => this.capture());
    this.el.torch.addEventListener("click", () => this.toggleTorch());
    this.onKey = (e) => {
      if (e.key === "Escape") this.close();
      else if ((e.key === " " || e.key === "Enter") && !this.el.shutter.disabled) {
        e.preventDefault();
        this.capture();
      }
    };
    document.addEventListener("keydown", this.onKey);
    this.start();
  }

  async start() {
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error("insecure");
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" }, // กล้องหลัง
          width: { ideal: 3840 },
          height: { ideal: 2160 },
        },
      });
      if (!this.isOpen) return this.stopStream(); // ผู้ใช้กดปิดระหว่างรอสิทธิ์
      const { video } = this.el;
      video.srcObject = this.stream;
      await video.play().catch(() => {});
      await this.waitForFrame();
      if (!this.isOpen) return;
      this.el.state.remove();
      this.el.shutter.disabled = false;
      this.el.shutter.focus({ preventScroll: true });
      this.setupTorch();
    } catch (err) {
      if (this.isOpen) this.showError(cameraError(err));
    }
  }

  waitForFrame() {
    const { video } = this.el;
    if (video.videoWidth) return Promise.resolve();
    return new Promise((resolve) => video.addEventListener("loadedmetadata", resolve, { once: true }));
  }

  setupTorch() {
    const track = this.stream?.getVideoTracks()[0];
    // บางเครื่องไม่บอก capability ก่อนภาพเฟรมแรกขึ้น จึงเช็กหลังภาพขึ้นแล้ว
    if (track?.getCapabilities?.().torch) this.el.torch.classList.remove("ghost");
    track?.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
  }

  async toggleTorch() {
    const track = this.stream?.getVideoTracks()[0];
    if (!track) return;
    const on = !this.el.torch.classList.contains("on");
    try {
      await track.applyConstraints({ advanced: [{ torch: on }] });
      this.el.torch.classList.toggle("on", on);
      this.el.torch.setAttribute("aria-pressed", String(on));
    } catch {
      this.el.torch.classList.add("ghost");
    }
  }

  showError(message) {
    const state = this.el.state;
    state.className = "state";
    state.innerHTML = `<div class="big">${svg("off").replace("<svg", '<svg style="width:56px;height:56px"')}</div>
      <p>${message}</p>
      <div class="actions">
        <button class="primary native" type="button">ใช้แอปกล้องของเครื่อง</button>
        <button class="secondary retry" type="button">ลองเปิดกล้องอีกครั้ง</button>
        <button class="secondary dismiss" type="button">ปิด</button>
      </div>`;
    state.querySelector(".native").addEventListener("click", () => {
      this.close();
      this.onNative(); // ยังอยู่ในจังหวะที่ผู้ใช้แตะ จึงเปิดหน้าเลือกไฟล์/กล้องได้
    });
    state.querySelector(".retry").addEventListener("click", () => {
      this.close();
      this.open();
    });
    state.querySelector(".dismiss").addEventListener("click", () => this.close());
  }

  capture() {
    const { video, shutter } = this.el;
    if (shutter.disabled || !video.videoWidth) return;
    shutter.disabled = true;
    const dataUrl = toJpeg(video, video.videoWidth, video.videoHeight);
    this.count += 1;
    navigator.vibrate?.(40);
    this.el.flash.classList.remove("go");
    void this.el.flash.offsetWidth; // เริ่มแอนิเมชันใหม่ทุกครั้ง
    this.el.flash.classList.add("go");
    this.onShot(dataUrl);

    if (!this.opts.multiple) {
      setTimeout(() => this.close(), 250);
      return;
    }
    this.el.thumbImg.src = dataUrl;
    this.el.count.textContent = String(this.count);
    this.el.thumb.hidden = false;
    this.el.done.disabled = false;
    this.toast(`${svg("check")} ถ่ายแล้ว ${this.count} แผ่น — วางแผ่นถัดไปได้เลย`);
    setTimeout(() => {
      if (this.isOpen) shutter.disabled = false;
    }, COOLDOWN_MS);
  }

  toast(html) {
    const t = this.el.toast;
    t.innerHTML = html;
    t.classList.add("show");
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => t.classList.remove("show"), 1800);
  }

  stopStream() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }

  close() {
    if (!this.isOpen) return;
    this.stopStream();
    document.removeEventListener("keydown", this.onKey);
    clearTimeout(this.toastTimer);
    this.host.remove();
    this.host = null;
    document.body.style.overflow = this.prevOverflow;
    this.count = 0;
  }
}

export default function (component) {
  const { data, key, parentElement, setTriggerValue } = component;
  const opts = data || {};

  const launch = document.createElement("div");
  launch.className = "cam-launch";
  launch.innerHTML = `
    <button class="cam-open" type="button">
      <span class="ic">${svg("camera")}</span>
      <span><b>${opts.open_label}</b><small>${opts.open_hint}</small></span>
    </button>
    <button class="cam-native" type="button">${svg("phone")} ใช้แอปกล้องของเครื่อง</button>
    <input class="cam-file" type="file" accept="image/*" capture="environment" hidden>
    <p class="cam-msg" role="status" hidden></p>`;
  parentElement.appendChild(launch);
  const fileInput = launch.querySelector(".cam-file");
  const msg = launch.querySelector(".cam-msg");
  const say = (text) => {
    msg.textContent = text;
    msg.hidden = !text;
  };

  const scanner = new Scanner(opts, {
    onShot: (dataUrl) => setTriggerValue("photo", dataUrl),
    onNative: () => fileInput.click(),
  });

  launch.querySelector(".cam-open").addEventListener("click", () => {
    say("");
    scanner.open();
  });
  launch.querySelector(".cam-native").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files?.[0];
    fileInput.value = ""; // ถ่ายภาพเดิมซ้ำได้
    if (!file) return;
    try {
      setTriggerValue("photo", await fileToJpeg(file));
    } catch {
      say("เปิดภาพนี้ไม่ได้ ลองถ่ายใหม่อีกครั้ง");
    }
  });

  // เปิดกล้องทันทีเมื่อเพิ่งเลือกโหมดกล้อง (token เปลี่ยน) ไม่ใช่ทุกครั้งที่หน้าวาดใหม่
  const token = opts.open_token || 0;
  if (token && opened[key] !== token) {
    opened[key] = token;
    scanner.open();
  }

  return () => {
    scanner.close();
    launch.remove();
  };
}
