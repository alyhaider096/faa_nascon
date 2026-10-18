import { useLocalSearchParams } from 'expo-router';
import React from 'react';
import { GuestExperience } from '../../../components/GuestExperience';
export default function GuestCostream() { const { id } = useLocalSearchParams<{ id: string }>(); return <GuestExperience id={id} mode="costream" />; }

