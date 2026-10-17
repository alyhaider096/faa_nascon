import { Redirect } from 'expo-router';
import { useApp } from '../state/AppContext';
export default function Index() { const { account } = useApp(); return <Redirect href={account ? '/(tabs)/fixtures' : '/login'} />; }
