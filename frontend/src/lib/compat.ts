/** Carrier × transport compatibility + per-transport param fields (mirrors backend). */

export const CARRIERS = ["jitsi", "wbstream", "telemost"];
export const TRANSPORTS = ["datachannel", "vp8channel", "seichannel", "videochannel"];

const COMPAT: Record<string, string[]> = {
  jitsi: ["datachannel", "vp8channel", "seichannel", "videochannel"],
  wbstream: ["vp8channel", "seichannel", "videochannel"],
  telemost: ["vp8channel", "videochannel"],
};

export function compatTransports(carrier: string): string[] {
  return COMPAT[carrier] ?? [];
}

export function isCompatible(carrier: string, transport: string): boolean {
  return compatTransports(carrier).includes(transport);
}

/** Instance fields editable per transport (match instance.py TRANSPORT_PARAM_DEFAULTS). */
export const PARAM_FIELDS: Record<string, string[]> = {
  vp8channel: ["vp8_fps", "vp8_batch"],
  seichannel: ["fps", "batch", "frag", "ack_ms"],
  videochannel: [
    "video_codec", "video_w", "video_h", "video_fps", "video_bitrate",
    "video_hw", "video_qr_recovery", "video_qr_size", "video_tile_module", "video_tile_rs",
  ],
};
