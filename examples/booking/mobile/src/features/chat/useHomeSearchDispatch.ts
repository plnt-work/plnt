// Home search dispatch — owns the WS connection that backs freeform
// queries from the Home pill / /search modal. Returns both the
// dispatcher and the surfaces that consume its replies:
//   - banner: latest say-reply newer than the last user message, with no
//     action. Rendered as a sticky strip in the Home bottom sheet.
//   - searchResultsPlaceIds: when the agent replies with
//     action.kind="search_results", these place_ids replace the
//     client-side text filter as the visible set.
//
// Mount this hook in exactly ONE place per session (Home). Other
// surfaces that want to push queries (e.g. /search modal) should write
// to the shared search store instead — Home subscribes and dispatches.
import { useCallback, useMemo, useRef, useState } from "react";
import { useWsChat, type Reply } from "./useWsChat";
import { freeformEnvelope } from "./envelope";
import { env } from "@/lib/env";

interface Opts {
  userLoc?: { lat: number; lng: number } | null;
}

const _pseudoUser = "m-anon";
const _pseudoSession = "s-home";

export interface HomeSearchBanner {
  text: string;
  seq: number;
  dismiss: () => void;
}

export interface HomeSearchHandle {
  dispatch: (text: string) => void;
  banner: HomeSearchBanner | null;
  /** When the agent replies with action.kind="search_results", these
   *  replace the client-side text filter. `null` = fall back to filter. */
  searchResultsPlaceIds: string[] | null;
}

export function useHomeSearchDispatch({ userLoc }: Opts): HomeSearchHandle {
  const tenantId = env.defaultTenant;
  const userIdRef = useRef(_pseudoUser);
  const sessionIdRef = useRef(_pseudoSession);

  const { send, items } = useWsChat({
    tenantId,
    sessionId: sessionIdRef.current,
    userId: userIdRef.current,
  });

  const [dismissedSeq, setDismissedSeq] = useState<number | null>(null);

  // Index of the last `user` echo in the timeline — used as the
  // "since last query" cursor. The WS echoes the user message back as
  // a role=user reply (see useWsChat); we use that, not a local ref,
  // so reconnects + replay stay coherent.
  const lastUserIdx = useMemo(() => {
    for (let i = items.length - 1; i >= 0; i--) {
      if (items[i].kind === "user") return i;
    }
    return -1;
  }, [items]);

  const latestSayAfterUser: Reply | null = useMemo(() => {
    for (let i = items.length - 1; i > lastUserIdx; i--) {
      const it = items[i];
      if (it.kind !== "reply") continue;
      if (it.reply.role !== "say") continue;
      return it.reply;
    }
    return null;
  }, [items, lastUserIdx]);

  const searchResultsPlaceIds = useMemo<string[] | null>(() => {
    if (!latestSayAfterUser) return null;
    const action = (latestSayAfterUser.content as { action?: { kind?: string; place_ids?: unknown } })
      .action;
    if (action?.kind !== "search_results") return null;
    return Array.isArray(action.place_ids)
      ? (action.place_ids as unknown[]).map(String)
      : [];
  }, [latestSayAfterUser]);

  const banner = useMemo<HomeSearchBanner | null>(() => {
    if (!latestSayAfterUser) return null;
    if (latestSayAfterUser.seq === dismissedSeq) return null;
    const content = latestSayAfterUser.content as { text?: string; action?: { kind?: string } };
    // Any action attached → handled elsewhere (search_results filters the
    // list; offer_slots/booking_* belong to the venue assistant surface).
    if (content.action?.kind) return null;
    const text = String(content.text || "").trim();
    if (!text) return null;
    return {
      text,
      seq: latestSayAfterUser.seq,
      dismiss: () => setDismissedSeq(latestSayAfterUser.seq),
    };
  }, [latestSayAfterUser, dismissedSeq]);

  const dispatch = useCallback(
    (text: string) => {
      const envelope = freeformEnvelope(text, { userLoc });
      send(envelope);
    },
    [send, userLoc],
  );

  return { dispatch, banner, searchResultsPlaceIds };
}
