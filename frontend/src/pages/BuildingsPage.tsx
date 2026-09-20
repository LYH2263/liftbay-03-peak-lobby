import { useEffect, useState } from "react";
import { api } from "../api/client";
type B = { id: number; name: string; floors: number; lobby_floor: number; peak_mode: boolean };
export default function BuildingsPage() {
  const [rows, setRows] = useState<B[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { api<B[]>("/buildings").then(setRows).catch(() => {}); }, []);
  async function toggle(b: B) {
    setErr("");
    try {
      const updated = await api<B>(`/buildings/${b.id}`, {
        method: "PATCH",
        body: JSON.stringify({ peak_mode: !b.peak_mode }),
      });
      setRows((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>楼栋</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>楼层数</th><th>大厅层</th><th>早高峰模式</th></tr></thead>
    <tbody>{rows.map(b => <tr key={b.id}>
      <td>{b.name}</td><td className="mono">{b.floors}</td><td className="mono">{b.lobby_floor}F</td>
      <td>
        <button
          className={`peak-toggle${b.peak_mode ? " peak-toggle--on" : ""}`}
          title={b.peak_mode ? "点击关闭早高峰" : "点击打开早高峰"}
          onClick={() => toggle(b)}
        >
          {b.peak_mode ? "高峰 ON" : "高峰 OFF"}
        </button>
      </td>
    </tr>)}</tbody></table>
    <p className="peak-hint">早高峰开启后：大厅层上行呼梯优先派给停在大厅的空闲/上行轿厢；满员轿厢不超载，改派次选或拒绝。</p>
  </>);
}
