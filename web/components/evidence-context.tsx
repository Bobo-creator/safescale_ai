"use client";

import { createContext, useContext } from "react";

export interface EvidenceLinks {
  /** The evidence card number for a recall (its rank), or null if it isn't in the list. */
  rankOf: (recallId: number) => number | null;
  /** Scroll to a recall's evidence card and highlight it. */
  focus: (recallId: number) => void;
}

export const EvidenceContext = createContext<EvidenceLinks>({
  rankOf: () => null,
  focus: () => {},
});

export const useEvidence = () => useContext(EvidenceContext);
