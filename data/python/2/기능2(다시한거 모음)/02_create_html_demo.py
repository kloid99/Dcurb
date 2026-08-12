"""실제 기능 2 결과 CSV로 오프라인 HTML 시연 파일을 생성합니다.

실행:
    python 02_create_html_demo.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"행정동코드": "string"})


def records(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    frame = read_csv(path).fillna("")
    if "행정동코드" in frame:
        frame["행정동코드"] = frame["행정동코드"].str.replace(
            r"\.0$", "", regex=True
        )
    return frame.to_dict(orient="records")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>D-Curb Guardian · Feature 2</title>
  <style>
    :root{--ink:#202020;--g1:#454545;--g2:#737373;--g3:#b7b7b7;--line:#dedede;--wash:#f4f4f4;--paper:#fff}
    *{box-sizing:border-box} body{margin:0;background:#ededed;color:var(--ink);font-family:"Malgun Gothic","Apple SD Gothic Neo",Arial,sans-serif}
    button,select{font:inherit}.app{max-width:1440px;margin:0 auto;min-height:100vh;background:var(--paper);display:grid;grid-template-columns:280px 1fr}
    aside{background:#f3f3f3;border-right:1px solid var(--line);padding:28px 22px;position:sticky;top:0;height:100vh;overflow:auto}
    main{padding:34px 38px 60px}.eyebrow{font-size:12px;letter-spacing:.15em;color:var(--g2);font-weight:700}.brand{font-size:23px;font-weight:800;margin:5px 0 28px}
    .label{display:block;font-size:12px;color:var(--g2);margin:18px 0 7px}.control{width:100%;border:1px solid #c9c9c9;background:#fff;border-radius:5px;padding:10px}
    .views{display:grid;gap:7px}.view{border:1px solid #c9c9c9;background:#fff;border-radius:5px;padding:10px;text-align:left;cursor:pointer}.view.active{background:#292929;color:#fff}
    h1{font-size:31px;margin:5px 0 8px}.lead{color:var(--g2);margin:0 0 22px}.badge{display:inline-block;background:#252525;color:#fff;border-radius:4px;padding:7px 11px;font-size:13px;font-weight:700}
    .outline{display:inline-block;border:1px solid #555;border-radius:4px;padding:6px 10px;font-size:12px;margin-left:7px}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin:16px 0}.metric{border:1px solid var(--line);border-radius:6px;padding:15px;background:#fff}
    .metric span{display:block;color:var(--g2);font-size:12px}.metric strong{display:block;font-size:22px;margin-top:7px}
    .panel{border:1px solid var(--line);border-radius:6px;background:#fff;padding:18px;margin:13px 0}.panel h3{margin:0 0 14px;font-size:17px}
    .grid2{display:grid;grid-template-columns:1.1fr 1fr;gap:14px}.barrow{display:grid;grid-template-columns:110px 1fr 48px;gap:9px;align-items:center;margin:12px 0;font-size:13px}
    .track{height:13px;background:#e8e8e8;border-radius:99px;overflow:hidden}.fill{height:100%;background:#474747;border-radius:99px}.score{text-align:right;font-weight:700}
    .radar{width:100%;height:350px}.radar text{font-size:12px;fill:#505050}.radar .grid{fill:none;stroke:#d6d6d6}.radar .axis{stroke:#dcdcdc}.radar .shape{fill:rgba(55,55,55,.16);stroke:#333;stroke-width:2}
    table{width:100%;border-collapse:collapse;font-size:13px}th{background:#444;color:#fff;padding:10px 9px;text-align:left}td{border-bottom:1px solid #e3e3e3;padding:9px}tbody tr:nth-child(even){background:#f5f5f5}
    .notice{border-left:4px solid #333;background:#f2f2f2;padding:13px 15px;margin:12px 0;line-height:1.6}.policy{border:1px solid var(--line);border-radius:6px;padding:13px;margin:8px 0}
    .timebars{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;align-items:end;height:260px;padding-top:20px}.timecol{height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:6px}
    .columns{height:190px;display:flex;align-items:flex-end;gap:5px}.vbar{width:22px;background:#3e3e3e}.vbar.light{background:#ababab}.time{font-size:12px}.legend{font-size:12px;color:#666;text-align:right}
    .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{border:1px solid var(--line);border-radius:6px;padding:16px}.card h3{margin-top:0}.muted{color:var(--g2);font-size:12px}.hidden{display:none}
    @media(max-width:980px){.app{grid-template-columns:1fr}aside{position:relative;height:auto}.metrics,.cards{grid-template-columns:1fr 1fr}.grid2{grid-template-columns:1fr}}
    @media(max-width:620px){main{padding:24px 18px}.metrics,.cards{grid-template-columns:1fr}.timebars{overflow-x:auto}}
  </style>
</head>
<body>
<div class="app">
  <aside>
    <div class="eyebrow">D-CURB GUARDIAN</div><div class="brand">Feature 2</div>
    <span class="label">사용자 화면</span>
    <div class="views">
      <button class="view active" data-view="public">지자체 담당자</button>
      <button class="view" data-view="logistics">물류기업 운영자</button>
      <button class="view" data-view="driver">배송기사</button>
      <button class="view" data-view="team">팀 기능 연결</button>
    </div>
    <span class="label">시군구</span><select id="district" class="control"></select>
    <span class="label">위험유형</span><select id="type" class="control"></select>
    <span class="label">행정동</span><select id="region" class="control"></select>
    <p class="muted" style="margin-top:22px">위험유형은 final_modelling.csv의 6개 DLFI 지표로 계산합니다.</p>
  </aside>
  <main>
    <div class="eyebrow">D-CURB GUARDIAN · FEATURE 2</div>
    <h1>행정동 위험유형 자동 분류</h1>
    <p class="lead">DLFI가 높은 이유를 주요 위험원인 TOP 3와 정책 검토 방향으로 설명합니다.</p>
    <div id="content"></div>
  </main>
</div>
<script>
const master=__MASTER__;
const logistics=__LOGISTICS__;
const driver=__DRIVER__;
const policyText=__POLICY__;
const riskColumns={
  "배송수요":"배송수요위험점수","하역공간 부족":"하역공간부족위험점수","단속반복":"단속반복위험점수",
  "보행충돌":"보행충돌위험점수","교통방해":"교통방해위험점수","안전취약":"안전취약위험점수"
};
const typeOrder=["배송수요 과밀형","하역공간 부족형","단속반복형","보행충돌형","교통방해형","안전취약형","복합위험형"];
let currentView="public";
const $=id=>document.getElementById(id);
function options(el,values,selected){el.innerHTML=values.map(v=>`<option ${v===selected?"selected":""}>${v}</option>`).join("")}
function filtered(){
  return master.filter(r=>($("district").value==="전체"||r.시군구===$("district").value)&&($("type").value==="전체"||r.기본위험유형===$("type").value));
}
function init(){
  options($("district"),["전체",...new Set(master.map(r=>r.시군구))],"전체");
  options($("type"),["전체",...typeOrder],"전체");
  refreshRegions();
  document.querySelectorAll(".view").forEach(b=>b.onclick=()=>{document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));b.classList.add("active");currentView=b.dataset.view;render()});
  $("district").onchange=refreshRegions;$("type").onchange=refreshRegions;$("region").onchange=render;
}
function refreshRegions(){const rows=filtered();const prior=$("region").value;options($("region"),rows.map(r=>`${r.시군구} ${r.행정동}`),rows.some(r=>`${r.시군구} ${r.행정동}`===prior)?prior:`${rows[0].시군구} ${rows[0].행정동}`);render()}
function selected(){return master.find(r=>`${r.시군구} ${r.행정동}`===$("region").value)||master[0]}
function metrics(items){return `<div class="metrics">${items.map(x=>`<div class="metric"><span>${x[0]}</span><strong>${x[1]}</strong></div>`).join("")}</div>`}
function topBars(r){return [1,2,3].map(i=>`<div class="barrow"><span>${r["주요위험요인"+i]}</span><div class="track"><div class="fill" style="width:${r["주요위험점수"+i]}%"></div></div><span class="score">${Number(r["주요위험점수"+i]).toFixed(1)}</span></div>`).join("")}
function radar(r){
  const labels=Object.keys(riskColumns),cx=190,cy=170,R=120;
  const point=(i,v)=>{const a=-Math.PI/2+i*2*Math.PI/labels.length;return [cx+Math.cos(a)*R*v/100,cy+Math.sin(a)*R*v/100]};
  const grids=[20,40,60,80,100].map(v=>`<polygon class="grid" points="${labels.map((_,i)=>point(i,v).join(",")).join(" ")}"/>`).join("");
  const axes=labels.map((_,i)=>{const p=point(i,100);return `<line class="axis" x1="${cx}" y1="${cy}" x2="${p[0]}" y2="${p[1]}"/>`}).join("");
  const shape=labels.map((l,i)=>point(i,Number(r[riskColumns[l]])).join(",")).join(" ");
  const text=labels.map((l,i)=>{const p=point(i,118);return `<text x="${p[0]}" y="${p[1]}" text-anchor="middle">${l}</text>`}).join("");
  return `<svg class="radar" viewBox="0 0 380 350">${grids}${axes}<polygon class="shape" points="${shape}"/>${text}</svg>`;
}
function similar(r){return master.filter(x=>x.기본위험유형===r.기본위험유형&&x.행정동코드!==r.행정동코드).map(x=>{let d=0;Object.values(riskColumns).forEach(c=>d+=(Number(x[c])-Number(r[c]))**2);return {...x,d:Math.sqrt(d/6)}}).sort((a,b)=>a.d-b.d).slice(0,5)}
function table(headers,rows){return `<table><thead><tr>${headers.map(h=>`<th>${h[0]}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${headers.map(h=>`<td>${r[h[1]]??""}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function publicView(r){
  const sim=similar(r).map(x=>({...x,지역명:`${x.시군구} ${x.행정동}`,지표거리:x.d.toFixed(1)}));
  return `<span class="badge">${r.위험유형}</span>${r.복합위험여부==="예"?'<span class="outline">복합위험</span>':""}
  <h2>${r.시군구} ${r.행정동}</h2>${metrics([["DLFI",Number(r.DLFI).toFixed(2)],["대전 순위",r.DLFI_순위+"위"],["TOP 1",Number(r.주요위험점수1).toFixed(1)],["지역특성",r.지역특성태그]])}
  <div class="notice"><strong>한 줄 자동 해석</strong><br>${r.한줄자동해석}</div>
  <div class="grid2"><section class="panel"><h3>6개 세부 지표</h3>${radar(r)}</section><section class="panel"><h3>주요 위험원인 TOP 3</h3>${topBars(r)}<p class="muted">${r.복합판정근거}</p></section></div>
  <section class="panel"><h3>유사 유형 지역</h3>${table([["지역","지역명"],["DLFI","DLFI"],["위험유형","위험유형"],["지표거리","지표거리"]],sim)}</section>
  <section class="panel"><h3>우선 검토 정책</h3>${String(r.권장정책).split(" + ").map((p,i)=>`<div class="policy"><strong>${i+1}순위</strong> · ${p}</div>`).join("")}</section>
  <section class="panel"><h3>분류 근거</h3><p>지역특성: ${r.지역특성근거}</p><p>K-Means 보조: 군집 ${r.기존KMeans군집_보조} · ${r.기존KMeans유형_보조}</p><p class="muted">K-Means는 최종 유형 판정에 사용하지 않습니다.</p></section>`;
}
function timeBars(rows,a,b){
  const max=Math.max(...rows.flatMap(r=>[Number(r[a])||0,Number(r[b])||0]),1);
  return `<div class="timebars">${rows.map(r=>`<div class="timecol"><div class="columns"><div class="vbar" title="${Number(r[a]).toFixed(1)}" style="height:${(Number(r[a])||0)/max*180}px"></div><div class="vbar light" title="${Number(r[b]).toFixed(1)}" style="height:${(Number(r[b])||0)/max*180}px"></div></div><span class="time">${r.시간대}</span></div>`).join("")}</div>`;
}
function logisticsView(r){
  const rows=logistics.filter(x=>String(x.행정동코드)===String(r.행정동코드)).sort((a,b)=>Number(a.동내_혼잡도순위)-Number(b.동내_혼잡도순위));
  if(!rows.length)return `<span class="badge">${r.위험유형}</span><h2>${r.행정동} 운영 참고</h2><div class="notice">logistics_view_timeband_v3.csv가 연결되지 않았습니다.</div>`;
  const best=rows[0];return `<span class="badge">${r.위험유형}</span><h2>${r.시군구} ${r.행정동} 운영 참고</h2>
  ${metrics([["DLFI",Number(r.DLFI).toFixed(2)],["혼잡이 낮은 시간대",best.시간대],["시간대 혼잡도",Number(best.혼잡도_시간대).toFixed(1)],["데이터 수단",best.데이터수단수]])}
  <section class="panel"><h3>시간대별 혼잡·배송집중</h3><div class="legend">■ 혼잡도　<span style="color:#aaa">■</span> 배송집중도</div>${timeBars(rows,"혼잡도_시간대","배송집중도_시간대")}</section>
  <section class="panel">${table([["순위","동내_혼잡도순위"],["시간대","시간대"],["혼잡도","혼잡도_시간대"],["배송집중도","배송집중도_시간대"],["수단 수","데이터수단수"]],rows)}</section>
  <div class="notice">시간대 데이터는 운영 참고 화면에만 사용하며 위험유형은 final_modelling.csv의 6개 지표로 계산합니다.</div>`;
}
function driverView(r){
  const rows=driver.filter(x=>String(x.행정동코드)===String(r.행정동코드)).sort((a,b)=>Number(a.동내_시간대순위)-Number(b.동내_시간대순위));
  if(!rows.length)return `<span class="badge">${r.위험유형}</span><h2>${r.행정동} 배송 주의</h2><div class="notice">driver_view_timeband_v3.csv가 연결되지 않았습니다.</div>`;
  const best=rows[0],map=Object.fromEntries(policyText.map(x=>[x.원본_추천정책_텍스트,x.기사용_안내문구])),guide=map[best.추천정책_텍스트]||"";
  return `<span class="badge">${r.위험유형}</span><h2>${r.시군구} ${r.행정동} 배송 주의</h2>
  ${metrics([["추천 시간대",best.시간대],["하역 등급",best.탄력하역권_등급_표시],["시간대 순위",best.동내_시간대순위+"위"],["실측검증",best.모델실측_검증플래그]])}
  ${guide?`<div class="notice"><strong>기사 안내</strong><br>${guide}</div>`:""}
  <section class="panel"><h3>시간대별 하역 안내</h3>${table([["순위","동내_시간대순위"],["시간대","시간대"],["등급","탄력하역권_등급_표시"],["혼잡도","혼잡도_시간대"],["신뢰","순위신뢰여부"],["실측검증","모델실측_검증플래그"]],rows)}</section>
  <p class="muted">현장 통제·표지·안전요원의 안내를 우선합니다.</p>`;
}
function teamView(){
  const rows=[
    {f:"final_modelling.csv",n:"82행",u:"기능 2 공식 분류 입력"},
    {f:"logistics_view_timeband_v3.csv",n:"492행",u:"물류기업 82동×6시간대"},
    {f:"driver_view_timeband_v3.csv",n:"492행",u:"배송기사 시간대·실측검증"},
    {f:"driver_facing_policy_text.csv",n:"11행",u:"기사 안내문구"},
    {f:"DLFI_탄력주정차_82동_대시보드용_v2.csv",n:"82행",u:"기능 1 연결"},
    {f:"탄력주정차_행정동매핑_DLFI조인_v2.csv",n:"55행",u:"기능 1 기존 지정구간"}
  ];
  return `<h2>팀 기능 연결</h2><div class="cards"><div class="card"><h3>① 하역공간 후보지</h3><p>행정동·위험유형·TOP 3를 후보지 우선순위에 전달합니다.</p></div><div class="card"><h3>③ 정책 What-if</h3><p>유형과 정책 검토안을 전달하며 효과 계산은 기능 3이 담당합니다.</p></div><div class="card"><h3>④ 데이터 신뢰도</h3><p>행정동코드로 신뢰도와 품질 플래그를 결합합니다.</p></div></div><section class="panel"><h3>확인한 통합 파일</h3>${table([["파일","f"],["규모","n"],["사용 목적","u"]],rows)}</section>`;
}
function render(){const r=selected();$("content").innerHTML=currentView==="public"?publicView(r):currentView==="logistics"?logisticsView(r):currentView==="driver"?driverView(r):teamView()}
init();
</script>
</body></html>"""


def create_demo(
    master: Path,
    logistics: Path | None,
    driver: Path | None,
    policy: Path | None,
    output: Path,
) -> None:
    html = HTML_TEMPLATE
    html = html.replace(
        "__MASTER__", json.dumps(records(master), ensure_ascii=False, separators=(",", ":"))
    )
    html = html.replace(
        "__LOGISTICS__",
        json.dumps(records(logistics), ensure_ascii=False, separators=(",", ":")),
    )
    html = html.replace(
        "__DRIVER__", json.dumps(records(driver), ensure_ascii=False, separators=(",", ":"))
    )
    html = html.replace(
        "__POLICY__", json.dumps(records(policy), ensure_ascii=False, separators=(",", ":"))
    )
    output.write_text(html, encoding="utf-8")
    print(f"[완료] {output}")


def parse_args() -> argparse.Namespace:
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=folder / "risk_type_master.csv")
    parser.add_argument(
        "--logistics",
        type=Path,
        default=folder / "input_data" / "logistics_view_timeband_v3.csv",
    )
    parser.add_argument(
        "--driver",
        type=Path,
        default=folder / "input_data" / "driver_view_timeband_v3.csv",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=folder / "input_data" / "driver_facing_policy_text.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=folder / "Feature2_Risk_Type_Demo.html",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    create_demo(args.master, args.logistics, args.driver, args.policy, args.output)

