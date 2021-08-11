from typing import List

import psycopg2
from more_itertools import flatten


def get_indexed_subgraphs(
    dbname: str, user: str, password: str, host: str
) -> List[str]:
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute(
        """
        select
        d.deployment
        from subgraphs.subgraph_deployment as d,
        subgraphs.subgraph_deployment_assignment as a,
        subgraphs.subgraph_version as v,
        subgraphs.subgraph as g,
        ethereum_networks as n,
        deployment_schemas as s
        where g.id = v.subgraph
        and v.id in (g.pending_version, g.current_version)
        and a.id = s.id
        and s.id = d.id
        and v.deployment = d.deployment
        and not d.failed
        and n.name = s.network
        and not a.node_id = 'removed';
        """
    )

    return flatten(cur.fetchall())
