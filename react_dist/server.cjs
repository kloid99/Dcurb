var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// server.ts
var import_express = __toESM(require("express"), 1);
var import_path2 = __toESM(require("path"), 1);
var import_fs2 = __toESM(require("fs"), 1);
var import_jszip = __toESM(require("jszip"), 1);
var import_vite = require("vite");

// src/server/weatherService.ts
var import_fs = __toESM(require("fs"), 1);
var import_path = __toESM(require("path"), 1);
var CACHE_TTL_MS = 30 * 60 * 1e3;
var memoryCache = null;
var lastFetchTimestamp = 0;
function readJsonFile(filename) {
  const primaryPath = import_path.default.join(process.cwd(), "data", filename);
  const fallbackPath = import_path.default.join(process.cwd(), filename);
  let targetPath = primaryPath;
  if (!import_fs.default.existsSync(primaryPath) && import_fs.default.existsSync(fallbackPath)) {
    targetPath = fallbackPath;
  }
  const raw = import_fs.default.readFileSync(targetPath, "utf-8");
  return JSON.parse(raw);
}
async function getWeatherData(forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && memoryCache && now - lastFetchTimestamp < CACHE_TTL_MS) {
    return memoryCache;
  }
  try {
    const weatherGridData = readJsonFile("weather_grid.json");
    const dongGeoData = readJsonFile("dong_geo.json");
    const grids = weatherGridData.grids;
    const lats = grids.map((g) => g.lat).join(",");
    const lons = grids.map((g) => g.lon).join(",");
    const apiUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lats}&longitude=${lons}&hourly=temperature_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m&timezone=Asia/Seoul&forecast_days=7`;
    const response = await fetch(apiUrl, { signal: AbortSignal.timeout(8e3) });
    if (!response.ok) {
      throw new Error(`Open-Meteo returned HTTP ${response.status}`);
    }
    const rawResult = await response.json();
    const forecastList = Array.isArray(rawResult) ? rawResult : [rawResult];
    const TIME_BLOCKS = [
      { id: "07~10", from: 7, to: 10 },
      { id: "10~12", from: 10, to: 12 },
      { id: "12~14", from: 12, to: 14 },
      { id: "14~17", from: 14, to: 17 },
      { id: "17~20", from: 17, to: 20 },
      { id: "20~23", from: 20, to: 23 }
    ];
    const gridForecasts = {};
    const dateSet = /* @__PURE__ */ new Set();
    grids.forEach((grid, index) => {
      const locForecast = forecastList[index] || forecastList[0];
      const hourly = locForecast?.hourly;
      if (!hourly || !hourly.time) return;
      const times = hourly.time;
      const temps = hourly.temperature_2m || [];
      const precips = hourly.precipitation || [];
      const probs = hourly.precipitation_probability || [];
      gridForecasts[grid.gridId] = {};
      for (let i = 0; i < times.length; i++) {
        const timeStr = times[i];
        const dateStr = timeStr.slice(0, 10);
        const hour = parseInt(timeStr.slice(11, 13), 10);
        dateSet.add(dateStr);
        if (!gridForecasts[grid.gridId][dateStr]) {
          gridForecasts[grid.gridId][dateStr] = {};
        }
        const block = TIME_BLOCKS.find((b) => hour >= b.from && hour < b.to);
        if (!block) continue;
        if (!gridForecasts[grid.gridId][dateStr][block.id]) {
          gridForecasts[grid.gridId][dateStr][block.id] = {
            score: 0,
            status: "\uC815\uC0C1 \uC6B4\uC601",
            reason: "\uAE30\uC0C1 \uC704\uD5D8 \uB0AE\uC74C",
            maxRainProb: 0,
            maxPrecipMm: 0,
            maxTempC: -99
          };
        }
        const currentBlock = gridForecasts[grid.gridId][dateStr][block.id];
        currentBlock.maxRainProb = Math.max(currentBlock.maxRainProb, probs[i] || 0);
        currentBlock.maxPrecipMm = Math.max(currentBlock.maxPrecipMm, precips[i] || 0);
        currentBlock.maxTempC = Math.max(currentBlock.maxTempC, temps[i] || 0);
      }
      Object.keys(gridForecasts[grid.gridId]).forEach((dStr) => {
        TIME_BLOCKS.forEach((block) => {
          const item = gridForecasts[grid.gridId][dStr][block.id];
          if (!item) return;
          let rainScore = 0;
          let rainReason = "";
          if (item.maxRainProb >= 80) {
            rainScore = 8;
            rainReason = "\uAC15\uC218\uD655\uB960 80% \uC774\uC0C1";
          } else if (item.maxRainProb >= 60) {
            rainScore = 5;
            rainReason = "\uAC15\uC218\uD655\uB960 60% \uC774\uC0C1";
          } else if (item.maxRainProb >= 40) {
            rainScore = 3;
            rainReason = "\uAC15\uC218\uD655\uB960 40% \uC774\uC0C1";
          }
          let precipScore = 0;
          let precipReason = "";
          if (item.maxPrecipMm > 0) {
            precipScore = 3;
            precipReason = "\uAC15\uC218 \uC608\uBCF4";
          }
          let tempScore = 0;
          let tempReason = "";
          if (item.maxTempC >= 33) {
            tempScore = 5;
            tempReason = "\uACE0\uC628 \uC704\uD5D8";
          }
          item.score = rainScore + precipScore + tempScore;
          const reasons = [];
          if (rainReason) reasons.push(rainReason);
          if (precipReason) reasons.push(precipReason);
          if (tempReason) reasons.push(tempReason);
          item.reason = reasons.length > 0 ? reasons.join(" / ") : "\uAE30\uC0C1 \uC704\uD5D8 \uB0AE\uC74C";
          if (item.score >= 10) {
            item.status = "\uBC30\uC1A1\uC2DC\uAC04 \uC870\uC815 \uAC80\uD1A0";
          } else if (item.score >= 5) {
            item.status = "\uC8FC\uC758 \uC6B4\uC601";
          } else {
            item.status = "\uC815\uC0C1 \uC6B4\uC601";
          }
        });
      });
    });
    const byDongCode = {};
    const sortedDates = Array.from(dateSet).sort();
    dongGeoData.dongs.forEach((dong) => {
      const gridFc = gridForecasts[dong.gridId] || {};
      byDongCode[dong.dongCode] = {
        dongCode: dong.dongCode,
        dong: dong.dong,
        gu: dong.gu,
        gridId: dong.gridId,
        forecast: gridFc
      };
    });
    const payload = {
      fetchedAt: (/* @__PURE__ */ new Date()).toISOString(),
      stale: false,
      dates: sortedDates,
      timeBlocks: ["07~10", "10~12", "12~14", "14~17", "17~20", "20~23"],
      byDongCode
    };
    memoryCache = payload;
    lastFetchTimestamp = now;
    return payload;
  } catch (err) {
    console.error("Failed to fetch Open-Meteo weather:", err);
    if (memoryCache) {
      return {
        ...memoryCache,
        stale: true
      };
    }
    const fallbackDates = [
      (/* @__PURE__ */ new Date()).toISOString().slice(0, 10),
      new Date(Date.now() + 864e5).toISOString().slice(0, 10),
      new Date(Date.now() + 864e5 * 2).toISOString().slice(0, 10),
      new Date(Date.now() + 864e5 * 3).toISOString().slice(0, 10),
      new Date(Date.now() + 864e5 * 4).toISOString().slice(0, 10),
      new Date(Date.now() + 864e5 * 5).toISOString().slice(0, 10),
      new Date(Date.now() + 864e5 * 6).toISOString().slice(0, 10)
    ];
    return {
      fetchedAt: (/* @__PURE__ */ new Date()).toISOString(),
      stale: true,
      error: "\uAE30\uC0C1 \uB370\uC774\uD130\uB97C \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4",
      dates: fallbackDates,
      timeBlocks: ["07~10", "10~12", "12~14", "14~17", "17~20", "20~23"],
      byDongCode: {}
    };
  }
}

// server.ts
var EXCLUDED_PATHS = ["node_modules", "dist", ".git", ".DS_Store", "package-lock.json"];
function getAllProjectFiles(dir, baseDir = dir) {
  let results = [];
  const list = import_fs2.default.readdirSync(dir);
  for (const file of list) {
    if (EXCLUDED_PATHS.includes(file)) continue;
    const fullPath = import_path2.default.join(dir, file);
    const relativePath = import_path2.default.relative(baseDir, fullPath);
    const stat = import_fs2.default.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getAllProjectFiles(fullPath, baseDir));
    } else {
      results.push({ relativePath, fullPath });
    }
  }
  return results;
}
async function startServer() {
  const app = (0, import_express.default)();
  const PORT = 3e3;
  app.use(import_express.default.json());
  app.get("/api/weather", async (req, res) => {
    const force = req.query.force === "true";
    const data = await getWeatherData(force);
    res.json(data);
  });
  app.get("/api/project-files", (req, res) => {
    try {
      const rootDir = process.cwd();
      const fileList = getAllProjectFiles(rootDir);
      const filesData = fileList.map((f) => {
        let content = "";
        try {
          content = import_fs2.default.readFileSync(f.fullPath, "utf-8");
        } catch {
          content = "[Binary or Unreadable Content]";
        }
        return {
          path: f.relativePath,
          content,
          size: import_fs2.default.statSync(f.fullPath).size
        };
      });
      res.json({ success: true, files: filesData });
    } catch (err) {
      res.status(500).json({ success: false, error: err.message });
    }
  });
  app.get("/api/download-zip", async (req, res) => {
    try {
      const zip = new import_jszip.default();
      const rootDir = process.cwd();
      const files = getAllProjectFiles(rootDir);
      for (const f of files) {
        try {
          const fileData = import_fs2.default.readFileSync(f.fullPath);
          zip.file(f.relativePath, fileData);
        } catch (e) {
          console.error(`Failed to include file ${f.relativePath}:`, e);
        }
      }
      const buffer = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
      res.setHeader("Content-Type", "application/zip");
      res.setHeader("Content-Disposition", 'attachment; filename="D-Curb-Guardian-SourceCode.zip"');
      res.send(buffer);
    } catch (err) {
      console.error("ZIP generation error:", err);
      res.status(500).json({ error: "Failed to generate ZIP archive" });
    }
  });
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", serverTime: (/* @__PURE__ */ new Date()).toISOString() });
  });
  if (process.env.NODE_ENV !== "production") {
    const vite = await (0, import_vite.createServer)({
      server: { middlewareMode: true },
      appType: "spa"
    });
    app.use(vite.middlewares);
  } else {
    const distPath = import_path2.default.join(process.cwd(), "dist");
    app.use(import_express.default.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(import_path2.default.join(distPath, "index.html"));
    });
  }
  app.listen(PORT, "0.0.0.0", () => {
    console.log(`D-Curb Guardian server running on http://0.0.0.0:${PORT}`);
  });
}
startServer();
//# sourceMappingURL=server.cjs.map
