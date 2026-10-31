import json
import time

_MEM = {}


def _binding(env, name):
    try:
        value = getattr(env, name)

    except Exception as error:
        print(f"Failed To Get Binding {name}: {error}")

        return None

    return value if value is not None else None


class Cache:
    def __init__(self, env):
        self._kv = _binding(env, "CACHE")

    async def get(self, key):
        hit = _MEM.get(key)

        if hit and hit[0] > time.time():
            return hit[1]

        if self._kv is not None:
            try:
                value = await self._kv.get(key, "json")

            except Exception as error:
                print(f"Failed To Get Cache Key {key}: {error}")

                value = None

            if value is not None:
                _MEM[key] = (time.time() + 60, value)
                return value

        return None

    async def set(self, key, value, ttl, persist=True):
        _MEM[key] = (time.time() + ttl, value)

        if persist and self._kv is not None:
            try:
                await self._kv.put(key, json.dumps(value), expirationTtl=ttl)

            except Exception as error:
                print(f"Failed To Set Cache Key {key}: {error}")
