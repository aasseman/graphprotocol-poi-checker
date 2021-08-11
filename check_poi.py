#!/usr/bin/env python3

import json
import os
import re
from string import Template
from typing import List

import base58
import configargparse
import requests

from db_utils import get_indexed_subgraphs


def to_id(hash):
    bytes_value = base58.b58decode(hash)
    hex_value = bytes_value.hex()
    return "0x" + hex_value[4:]


def to_ipfs_hash(id):
    # https://ethereum.stackexchange.com/questions/17094/how-to-store-ipfs-hash-using-bytes32
    hex_value = bytes.fromhex("1220" + id[2:])
    ipfs_hash = base58.b58encode(hex_value)
    return ipfs_hash.decode("utf-8")


def generate_poi(indexer_id, block_number, block_hash, subgraph_ipfs_hash):
    t = Template(
        """query MyQuery {
        proofOfIndexing(
          subgraph: "$subgraph_ipfs_hash",
          blockNumber: $block_number,
          blockHash: "$block_hash",
          indexer: "$indexer_id")
       }"""
    )
    query_data = t.substitute(
        subgraph_ipfs_hash=subgraph_ipfs_hash,
        block_number=block_number,
        block_hash=block_hash,
        indexer_id=indexer_id,
    )
    request = requests.post(local_index_node_endpoint, json={"query": query_data})

    if request.status_code != 200:
        print("error in generate_poi")
        print(request.text)
        os._exit(1)

    json_response = json.loads(request.text)

    if "errors" in json_response:
        print("error in generate_poi")
        print(json_response["errors"])
        os._exit(1)

    return json_response["data"]["proofOfIndexing"]


def convert_tokens(amount):
    if len(amount) <= 18:
        return "~0"
    else:
        return str(amount[:-18])


def get_indexers_poi_epoch(subgraph, zero_pois):
    indexers_poi_epoch = []
    if indexers_list == '["all"]':
        t = Template(
            """query MyQuery {
          allocations(where: {subgraphDeployment: "$subgraph", $zero_pois status_not: Active }, first: $number_allocation_to_check, orderBy: closedAtEpoch, orderDirection: desc) {
            closedAtEpoch
            indexer {
             id
            }
            allocatedTokens
            poi
          }
        }"""
        )
        query_data = t.substitute(
            subgraph=subgraph,
            number_allocation_to_check=number_allocation_to_check,
            zero_pois=zero_pois,
        )
    else:
        t = Template(
            """query MyQuery {
          allocations(where: {subgraphDeployment: "$subgraph", $zero_pois status_not: Active, indexer_in: $indexers_list }, first: $number_allocation_to_check, orderBy: closedAtEpoch, orderDirection: desc) {
            closedAtEpoch
            indexer {
             id
            }
            poi
            allocatedTokens
          }
        }"""
        )
        query_data = t.substitute(
            subgraph=subgraph,
            number_allocation_to_check=number_allocation_to_check,
            indexers_list=indexers_list,
            zero_pois=zero_pois,
        )

    request = requests.post(graph_endpoint, json={"query": query_data})

    if request.status_code != 200:
        print("error in get_indexers_poi_epoch")
        print(request.text)
        os._exit(1)

    json_response = json.loads(request.text)

    if "errors" in json_response:
        print("error in get_indexers_poi_epoch")
        print(json_response["errors"])
        os._exit(1)

    for i in json_response["data"]["allocations"]:
        indexers_poi_epoch.append(
            {
                "indexer_id": i["indexer"]["id"],
                "epoch": i["closedAtEpoch"],
                "poi": i["poi"],
                "allocatedTokens": convert_tokens(str(i["allocatedTokens"])),
            }
        )

    return indexers_poi_epoch


def get_current_epoch():
    query_data = "{\n graphNetworks {\n currentEpoch \n} \n}"
    request = requests.post(graph_endpoint, json={"query": query_data})

    if request.status_code != 200:
        print("error in get_current_epoch")
        print(request.text)
        os._exit(1)

    json_response = json.loads(request.text)

    if "errors" in json_response:
        print("error in get_current_epoch")
        print(json_response["errors"])
        os._exit(1)

    return json_response["data"]["graphNetworks"][0]["currentEpoch"]


def get_start_block(epoch):
    t = Template("{ epoch(id: $epoch) { startBlock } }")
    query_data = t.substitute(epoch=epoch)
    request = requests.post(graph_endpoint, json={"query": query_data})

    if request.status_code != 200:
        print("error in get_start_block")
        print(request.text)
        os._exit(1)

    json_response = json.loads(request.text)

    if "errors" in json_response:
        print("error in get_start_block")
        print(json_response["errors"])
        os._exit(1)

    return json_response["data"]["epoch"]["startBlock"]


def get_start_block_hash(epoch_start_block):
    payload = {
        "method": "eth_getBlockByNumber",
        "params": ["{}".format(hex(epoch_start_block)), False],
        "jsonrpc": "2.0",
        "id": 1,
    }

    response = requests.post(block_hash_endpoint, json=payload).json()

    if "error" in response:
        print("error in get_start_block_hash")
        print(response["error"])
        os._exit(1)

    return response["result"]["hash"]


# Dirty hack to replace ' for "
def convert_to_proper_indexer_list(indexers_list):
    indexers_list_array = indexers_list.split(",")
    indexers_list_converted = str(indexers_list_array).replace("'", '"')
    return indexers_list_converted


if __name__ == "__main__":
    parser = configargparse.ArgParser()
    parser.add_argument(
        "--graph_endpoint",
        env_var="GRAPH_ENDPOINT",
        help="graph network endpoint (default: %(default)s)",
        default="https://gateway.network.thegraph.com/network",
        type=str,
    )
    parser.add_argument(
        "--local_index_node_endpoint",
        env_var="INDEX_NODE_ENDPOINT",
        help="local index node endpoint (default: %(default)s)",
        default="http://index-node:8030/graphql",
        type=str,
    )
    parser.add_argument(
        "--ethereum",
        env_var="ETHEREUM",
        help="ethereum endpoint to request block hash (default: %(default)s)",
        default="https://eth-mainnet.alchemyapi.io/v2/demo",
        type=str,
    )
    parser.add_argument(
        "--num_check",
        env_var="NUM_CHECK",
        help="number of last closed allocation to check poi (default: %(default)s)",
        default=10,
        type=int,
    )
    parser.add_argument(
        "--indexers",
        env_var="INDEXERS",
        help="comma separated list of indexers to check poi with (default: %(default)s)",
        default="all",
        type=str,
    )
    parser.add_argument(
        "--no-zero-pois",
        env_var="NO_ZERO_POIS",
        help="do not include allocations with zero pois (default: %(default)s)",
        action="store_true",
    )
    parser.add_argument(
        "--db-name",
        env_var="DB_NAME",
        help="",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--db-user",
        env_var="DB_USER",
        help="",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--db-password",
        env_var="DB_PASSWORD",
        help="",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--db-host",
        env_var="DB_HOST",
        help="",
        required=True,
        type=str,
    )
    args = parser.parse_args()

    subgraph_ipfs_hashes = get_indexed_subgraphs(
        dbname=args.db_name,
        user=args.db_user,
        password=args.db_password,
        host=args.db_host,
    )
    graph_endpoint: str = args.graph_endpoint
    local_index_node_endpoint: str = args.local_index_node_endpoint
    block_hash_endpoint: str = args.ethereum
    number_allocation_to_check: int = args.num_check
    indexers_list: List[str] = convert_to_proper_indexer_list(args.indexers)

    # Remove network name -- such as 'mainnet:' -- at the beginning if present
    block_hash_endpoint = re.sub(r".*:(?=https?://)", "", block_hash_endpoint)

    if args.no_zero_pois:
        zero_pois = 'poi_not: "0x0000000000000000000000000000000000000000000000000000000000000000",'
    else:
        zero_pois = ""

    for subgraph_ipfs_hash in subgraph_ipfs_hashes:
        print("#" * 80)
        print("Start to check POI for subgraph: {}".format(subgraph_ipfs_hash))
        print("#" * 80)

        subgraph_deployment_id = to_id(subgraph_ipfs_hash)
        current_epoch = get_current_epoch()
        print("Current Epoch: {}".format(current_epoch))
        indexers_poi_epoch = get_indexers_poi_epoch(subgraph_deployment_id, zero_pois)

        for i in indexers_poi_epoch:
            start_block = get_start_block(i["epoch"])
            start_block_hash = get_start_block_hash(start_block)
            my_poi = generate_poi(
                i["indexer_id"], start_block, start_block_hash, subgraph_ipfs_hash
            )

            print()
            if my_poi != i["poi"]:
                previous_start_block = get_start_block(i["epoch"] - 1)
                previous_start_block_hash = get_start_block_hash(previous_start_block)
                previous_my_poi = generate_poi(
                    i["indexer_id"],
                    previous_start_block,
                    previous_start_block_hash,
                    subgraph_ipfs_hash,
                )
                if previous_my_poi != i["poi"]:
                    print(
                        "FAILED: POI missmatched with indexer {0}. Generated POI: {1} Indexer POI: {2} Allocation was closed in {3} EPOCH. Allocated Tokens: {4}".format(
                            i["indexer_id"],
                            my_poi,
                            i["poi"],
                            i["epoch"],
                            i["allocatedTokens"],
                        )
                    )
                else:
                    print(
                        "OK: POI matched with indexer {0} for epoch {2}. Allocation was closed in {1} EPOCH. Allocated Tokens: {3}".format(
                            i["indexer_id"],
                            i["epoch"],
                            i["epoch"] - 1,
                            i["allocatedTokens"],
                        )
                    )
            else:
                print(
                    "OK: POI matched with indexer {0}. Allocation was closed in {1} EPOCH. Allocated Tokens: {2}".format(
                        i["indexer_id"], i["epoch"], i["allocatedTokens"]
                    )
                )
        print()
