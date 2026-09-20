from fastapi import APIRouter, Depends, Query

from .. import services as svc
from ..models import NetworkEdge, NetworkNode, NetworkResponse, UserOut
from ..security import current_user

router = APIRouter(prefix="/api/v1/network", tags=["network"])


@router.get("", response_model=NetworkResponse)
def network(user: UserOut = Depends(current_user),
            limit: int = Query(120, ge=10, le=400)):
    """
    Asset/vulnerability graph for the 3D cyber-risk network view.

    Capped by default: past a few hundred nodes the force layout stops being
    readable and the browser starts dropping frames.
    """
    assets = svc.load_csv("assets")
    vulns = svc.vulnerabilities()
    graph = svc.graph_data()

    eal_by_asset = {
        a.get("asset_id"): a.get("risk_score", 0) * 1_000_000
        for a in graph.get("asset_risk_scores", [])
    }

    nodes: list[NetworkNode] = []
    edges: list[NetworkEdge] = []

    if not assets.empty:
        subset = assets.copy()
        if "asset_criticality" in subset.columns:
            subset["_crit_score"] = svc.numeric_criticality(subset["asset_criticality"])
            subset = subset.sort_values("_crit_score", ascending=False)
        subset = subset.head(limit)

        for r in subset.to_dict("records"):
            aid = str(r.get("asset_id"))
            crit = svc.CRITICALITY_LABEL_SCORE.get(r.get("asset_criticality"), 3)
            nodes.append(NetworkNode(
                id=aid,
                label=str(r.get("asset_name", aid)),
                type="asset",
                risk_level=svc.risk_level_from_score(crit / 5 * 100),
                expected_annual_loss=eal_by_asset.get(aid, 0.0),
                criticality=crit,
            ))

            bu = r.get("business_unit_id")
            if bu:
                edges.append(NetworkEdge(source=str(bu), target=aid, kind="owns", weight=crit))

        # Business units as parent nodes for the ones actually referenced.
        units = svc.load_csv("business_units")
        referenced = {e.source for e in edges}
        if not units.empty:
            for r in units.to_dict("records"):
                bid = str(r.get("business_unit_id"))
                if bid not in referenced:
                    continue
                nodes.append(NetworkNode(
                    id=bid,
                    label=str(r.get("business_unit_name", bid)),
                    type="business_unit",
                    risk_level=svc.risk_level_from_score(
                        float(r.get("criticality_score", 3) or 3) / 5 * 100),
                    criticality=float(r.get("criticality_score", 3) or 3),
                ))

        # Attach the most severe vulnerability per asset, so edges mean something.
        if not vulns.empty:
            asset_ids = {n.id for n in nodes if n.type == "asset"}
            relevant = vulns[vulns["asset_id"].astype(str).isin(asset_ids)]
            relevant = relevant.sort_values("cvss_score", ascending=False).head(limit * 2)
            for r in relevant.to_dict("records"):
                vid = str(r.get("vulnerability_id"))
                nodes.append(NetworkNode(
                    id=vid,
                    label=str(r.get("cve_id") or r.get("vulnerability_type", vid)),
                    type="vulnerability",
                    risk_level=r.get("risk_level", "Low"),
                    expected_annual_loss=0.0,
                ))
                edges.append(NetworkEdge(
                    source=vid, target=str(r.get("asset_id")),
                    kind="exposes", weight=float(r.get("cvss_score", 0) or 0),
                ))

    attack = graph.get("attack_paths", {})
    return NetworkResponse(
        nodes=nodes,
        edges=edges,
        attack_paths=attack.get("top_paths", []),
        stats={
            "nodes": len(nodes),
            "edges": len(edges),
            "assets": sum(1 for n in nodes if n.type == "asset"),
            "vulnerabilities": sum(1 for n in nodes if n.type == "vulnerability"),
            "attack_paths": attack.get("total_paths_found", 0),
        },
    )
