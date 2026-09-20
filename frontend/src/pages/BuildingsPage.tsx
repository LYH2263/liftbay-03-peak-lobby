import { useEffect, useState } from "react";
import { api } from "../api/client";
type B = { id: number; name: string; floors: number; lobby_floor: number; peak_mode: boolean };
export default function BuildingsPage() {
  const [rows, setRows] = useState<B[]>([]);
  const [err, setErr] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const reload = () => api<B[]>("/buildings").then(setRows);
  useEffect(() => { reload(); }, []);
  async function togglePeak(b: B) {
    setErr(""); setSavingId(b.id);
    try {
      const next = !b.peak_mode;
      const updated = await api<B>(`/buildings/${b.id}`, {
        method: "PATCH",
        body: JSON.stringify({ peak_mode: next }),
      });
      setRows((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingId(null);
    }
  }
  return (<>
    <h2>楼栋</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>楼层数</th><th>大厅层</th><th>早高峰</th></tr></thead>
    <tbody>{rows.map(b => <tr key={b.id}>
      <td>{b.name}</td>
      <td className="mono">{b.floors}</td>
      <td className="mono">{b.lobby_floor}F</td>
      <td>
        <label style={{ display: "inline-flex", gap: ".5rem", alignItems: "center", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={b.peak_mode}
            disabled={savingId === b.id}
            onChange={() => togglePeak(b)}
          />
          <span className={b.peak_mode ? "ok" : ""}>{b.peak_mode ? "开启" : "关闭"}</span>
        </label>
      </td>
    </tr>)}</tbody></table>
    <p className="dispatch-deck-hint" style={{ marginTop: ".75rem" }}>
      开启后，大厅层上行呼梯优先派给停在大厅的空闲/上行车；满员不超载，改派次选或拒绝。
    </p>
  </>);
}
