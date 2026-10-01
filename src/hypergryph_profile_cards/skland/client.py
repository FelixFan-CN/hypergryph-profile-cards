"""森空岛（Skland）客户端。

负责鹰角通行证 token -> grant code -> cred 的认证链路，以及带 sign 的接口请求。

!! 请注意 !!
森空岛是非官方接口，鹰角可能随时调整签名方式或字段。所有可变点集中在
下面的「可变常量」区，接口失效时优先改这里。

认证链路（对真实账号验证通过）：
    1. POST as.hypergryph.com/user/oauth2/v2/grant                  -> grant code
    2. POST zonai.skland.com/api/v1/user/auth/generate_cred_by_code
       该接口必须使用 iOS 客户端身份（os / platform / manufacturer / nid / vName），
       且【不需要】dId 与 sign；用 Android 身份或带随机 dId 都会返回
       code 10001「设备信息无效」。
    3. 后续游戏数据接口使用 cred + sign 签名请求。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse

import requests

from ..errors import SklandError

# ---------- 可变常量（接口变更时优先检查这里） ----------

AS_HOST = "https://as.hypergryph.com"
ZONAI_HOST = "https://zonai.skland.com"

# 明日方舟在鹰角通行证体系中的哈希 appCode（仅换取 grant code 时使用）
APP_CODE_ARKNIGHTS = "4ca99fa6b56cc2ba"

# 绑定列表里区分游戏的字符串 appCode（与上面的哈希 appCode 不是一回事）
BINDING_APP_CODE_ARKNIGHTS = "arknights"

# iOS 客户端身份：换取 cred 时必须带上，否则会被判定「设备信息无效」
CLIENT_VERSION = "1.0.1"
USER_AGENT = (
    f"Skland/{CLIENT_VERSION} (com.hypergryph.skland; build:100101; "
    "iOS 16.5.1) Alamofire/5.7.1"
)
IDENTITY_HEADERS = {
    "User-Agent": USER_AGENT,
    "os": "iOS",
    "platform": "2",
    "manufacturer": "Apple",
    "nid": "1",
    "vName": CLIENT_VERSION,
}

# 签名时间戳刻意回拨 2 秒，规避客户端与服务端的时钟偏差
SIGN_TIME_OFFSET = 2
TIMEOUT = 20


def unwrap(payload: dict, context: str) -> dict:
    """兼容两种响应外壳：as 域的 status，zonai 域的 code。"""
    code = payload.get("code", payload.get("status"))
    if code != 0:
        message = payload.get("message") or payload.get("msg") or payload
        raise SklandError(f"{context} 失败：{message}")
    return payload.get("data") or {}


def build_signed_headers(sign_token: str, path: str, query_string: str, cred: str) -> dict:
    """构造带 sign 的请求头。

    签名算法：
        sign = md5(hmac_sha256(sign_token, path + query_string + timestamp + header_json))
    query_string 【不含】前导问号；header_json 固定为
    {"platform":"","timestamp":...,"dId":"","vName":""} 的紧凑 JSON
    （与已上线实现保持一致：仅 timestamp 参与，其余留空）。
    """
    timestamp = str(int(time.time()) - SIGN_TIME_OFFSET)
    sign_fields = {"platform": "", "timestamp": timestamp, "dId": "", "vName": ""}
    header_json = json.dumps(sign_fields, separators=(",", ":"))
    digest = hmac.new(
        sign_token.encode(),
        (path + query_string + timestamp + header_json).encode(),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "cred": cred,
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
        "Connection": "close",
        "sign": hashlib.md5(digest.encode()).hexdigest(),
    }
    headers.update(sign_fields)
    return headers


def get_grant_code(hg_token: str) -> str:
    """用鹰角通行证 token 换取一次性 grant code。"""
    resp = requests.post(
        f"{AS_HOST}/user/oauth2/v2/grant",
        json={"appCode": APP_CODE_ARKNIGHTS, "token": hg_token, "type": 0},
        headers=IDENTITY_HEADERS,
        timeout=TIMEOUT,
    )
    return unwrap(resp.json(), "获取 grant code")["code"]


def get_cred(grant_code: str) -> tuple[str, str]:
    """用 grant code 换取 cred；同时返回后续签名用的 sign token。"""
    resp = requests.post(
        f"{ZONAI_HOST}/api/v1/user/auth/generate_cred_by_code",
        json={"code": grant_code, "kind": 1},
        headers=IDENTITY_HEADERS,
        timeout=TIMEOUT,
    )
    data = unwrap(resp.json(), "换取 cred")
    return data["cred"], data["token"]


def api_get(path: str, query: dict, cred: str, sign_token: str) -> dict:
    """发起一个带签名的 GET 请求。"""
    query_string = urllib.parse.urlencode(query) if query else ""
    headers = build_signed_headers(sign_token, path, query_string, cred)
    url = f"{ZONAI_HOST}{path}" + (f"?{query_string}" if query_string else "")
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    return unwrap(resp.json(), f"GET {path}")


def get_bindings(cred: str, sign_token: str) -> dict:
    """获取账号下已绑定的游戏角色列表。"""
    return api_get("/api/v1/game/player/binding", {}, cred, sign_token)


def get_arknights_player_info(cred: str, sign_token: str, uid: str) -> dict:
    """获取明日方舟玩家详情（含 status / chars / charInfoMap / routine 等）。"""
    return api_get("/api/v1/game/player/info", {"uid": uid}, cred, sign_token)


def resolve_arknights_uid(bindings: dict, preferred_uid: str | None = None) -> str | None:
    """从绑定列表中取出明日方舟的 uid。

    传入 preferred_uid 时优先校验它是否在绑定列表内，避免拉错账号。
    """
    for item in bindings.get("list", []):
        if item.get("appCode") != BINDING_APP_CODE_ARKNIGHTS:
            continue
        entries = item.get("bindingList") or []
        if preferred_uid:
            for entry in entries:
                if str(entry.get("uid")) == str(preferred_uid):
                    return str(entry["uid"])
        if entries:
            default = next((e for e in entries if e.get("isDefault")), entries[0])
            return str(default["uid"])
    return None


def fetch_arknights(hg_token: str, preferred_uid: str | None = None) -> dict:
    """完整链路：token -> cred -> 绑定列表 -> 玩家详情。"""
    grant_code = get_grant_code(hg_token)
    cred, sign_token = get_cred(grant_code)
    bindings = get_bindings(cred, sign_token)
    uid = resolve_arknights_uid(bindings, preferred_uid)
    if not uid:
        raise SklandError("该账号下没有找到明日方舟角色，请先在森空岛绑定游戏角色")
    return get_arknights_player_info(cred, sign_token, uid)
