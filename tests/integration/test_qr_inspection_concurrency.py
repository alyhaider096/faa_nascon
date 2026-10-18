"""Inspection deduplication must not cache state or cancel surviving viewers."""
import asyncio

from app.api import day2


def test_overlapping_inspections_share_read_but_next_request_is_fresh(monkeypatch):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def read(_fn, entity_id, **kwargs):
            calls.append((entity_id, kwargs))
            entered.set()
            await release.wait()
            return {"version": len(calls)}

        monkeypatch.setattr(day2, "run_tx", read)
        viewers = [asyncio.create_task(day2._inspect_qr("match-m1", "desktop"))
                   for _ in range(50)]
        await entered.wait()
        await asyncio.sleep(0)
        viewers[0].cancel()
        await asyncio.gather(viewers[0], return_exceptions=True)
        release.set()
        results = await asyncio.gather(*viewers[1:])
        assert results == [{"version": 1}] * 49
        assert len(calls) == 1
        assert await day2._inspect_qr("match-m1", "desktop") == {"version": 2}
        assert not day2._qr_inspections

    asyncio.run(scenario())


def test_failed_inspection_can_be_retried(monkeypatch):
    async def scenario():
        calls = 0

        async def read(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("read failed")
            return {"fresh": True}

        monkeypatch.setattr(day2, "run_tx", read)
        try:
            await day2._inspect_qr("match-m1", "desktop")
        except ValueError:
            pass
        else:
            raise AssertionError("failure must reach the viewer")
        assert await day2._inspect_qr("match-m1", "desktop") == {"fresh": True}
        assert not day2._qr_inspections

    asyncio.run(scenario())
