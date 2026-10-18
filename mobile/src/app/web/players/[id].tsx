import { useLocalSearchParams } from 'expo-router';
import React from 'react';
import { PublicProfile } from '../../../components/PublicProfile';
export default function PlayerProfile() { const { id } = useLocalSearchParams<{ id: string }>(); return <PublicProfile type="player" id={id} />; }

