/**
 * BusinessHeader — top of the right rail when a business is selected.
 *
 * Layout:
 *
 *   ┌────────────────────────────────────────┐
 *   │ [photo or vertical mark]               │
 *   ├────────────────────────────────────────┤
 *   │ Display Name                           │
 *   │ ★ 4.4  ·  1,210 reviews   [Restaurant] │
 *   │ Mon–Sat 9am – 7pm                      │
 *   │ Address line                           │
 *   │                                        │
 *   │ [📞 Call] [🌐 Website] [📍 Directions] │
 *   └────────────────────────────────────────┘
 *
 * Rating + review count come from the seed (and later /v1/places/area).
 * `photo_uri` is optional — when absent we render a soft vertical-tinted
 * gradient mark; never a fake star pattern or compass SVG. Buttons are
 * plain outline links — phone/web are href shortcuts, directions opens
 * the Google Maps deep link.
 */
import { Phone, Globe, MapPin } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/Tooltip";

import type { Business } from "./types";
import { metaFor } from "./verticals";

interface Props {
  business: Business;
}

export default function BusinessHeader({ business }: Props) {
  const meta = metaFor(business.vertical);
  const dirHref = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(
    `${business.lat},${business.lng}`,
  )}&destination_place_id=${encodeURIComponent(business.place_id)}`;

  return (
    <header className="px-4 pt-4 pb-3 border-b border-paper-500/60">
      <div
        className="h-32 rounded-lg overflow-hidden mb-3 relative"
        style={{
          background: business.photo_uri
            ? `center/cover url(${business.photo_uri})`
            : `linear-gradient(135deg, ${meta.color}33 0%, ${meta.color}1a 50%, ${meta.border}26 100%)`,
        }}
      >
        {!business.photo_uri && (
          <div
            className="absolute inset-0 flex items-end p-3 text-[11px] uppercase tracking-wide font-medium"
            style={{ color: meta.border }}
          >
            {meta.label.slice(0, -1)}
          </div>
        )}
      </div>

      <h2 className="text-lg font-semibold text-ink-700 leading-tight">
        {business.display_name}
      </h2>

      <div className="mt-1 flex items-center gap-2 flex-wrap text-[12.5px] text-ink-200">
        <span className="font-mono">★ {business.rating.toFixed(1)}</span>
        <span>·</span>
        <span>{business.user_ratings.toLocaleString()} reviews</span>
        <span
          className="ml-1 px-2 py-0.5 rounded-full text-[10.5px] font-medium uppercase tracking-wide"
          style={{ background: `${meta.color}1a`, color: meta.border }}
        >
          {meta.label.slice(0, -1)}
        </span>
      </div>

      {business.hours && (
        <div className="mt-1 text-[12px] text-ink-100">{business.hours}</div>
      )}
      <div className="mt-0.5 text-[12px] text-ink-100">{business.address}</div>

      <div className="mt-3 flex gap-2">
        {business.phone && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild size="sm" variant="outline">
                <a href={`tel:${business.phone.replace(/\s+/g, "")}`}>
                  <Phone className="size-3.5" />
                  <span>Call</span>
                </a>
              </Button>
            </TooltipTrigger>
            <TooltipContent>{business.phone}</TooltipContent>
          </Tooltip>
        )}
        {business.web && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild size="sm" variant="outline">
                <a href={business.web} target="_blank" rel="noreferrer noopener">
                  <Globe className="size-3.5" />
                  <span>Website</span>
                </a>
              </Button>
            </TooltipTrigger>
            <TooltipContent>{business.web}</TooltipContent>
          </Tooltip>
        )}
        <Button asChild size="sm" variant="outline">
          <a href={dirHref} target="_blank" rel="noreferrer noopener">
            <MapPin className="size-3.5" />
            <span>Directions</span>
          </a>
        </Button>
      </div>
    </header>
  );
}
