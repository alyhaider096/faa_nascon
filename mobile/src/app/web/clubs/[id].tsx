import { useLocalSearchParams } from 'expo-router';
import React from 'react';
import { PublicProfile } from '../../../components/PublicProfile';
export default function ClubProfile() { const { id } = useLocalSearchParams<{ id: string }>(); return <PublicProfile type="club" id={id} />; }

