export type WhipPublisherHandle = {
  start: (endpoint: string, bearer?: string) => Promise<void>;
  stop: () => Promise<void>;
};
export const WhipPublisher: import('react').ForwardRefExoticComponent<{
  onState: (state: 'idle' | 'connecting' | 'live' | 'degraded' | 'stopped') => void;
} & import('react').RefAttributes<WhipPublisherHandle>>;
