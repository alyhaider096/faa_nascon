import React from 'react';

export type LiveVideoHandle = {
  currentTime: () => number;
  restore: (seconds: number, shouldPlay: boolean) => void;
  isPlaying: () => boolean;
};

export const LiveVideo: React.ForwardRefExoticComponent<
  { uri: string | null; label: string } & React.RefAttributes<LiveVideoHandle>
>;
