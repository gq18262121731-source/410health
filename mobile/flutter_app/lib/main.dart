import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/network/api_client.dart';
import 'core/network/server_endpoint_config.dart';
import 'features/auth/providers/auth_provider.dart';
import 'features/auth/repositories/auth_repository.dart';
import 'features/auth/screens/login_screen.dart';
import 'features/alarm/repositories/alarm_repository.dart';
import 'features/alarm/providers/alarm_provider.dart';
import 'features/alarm/widgets/global_alarm_listener.dart';
import 'features/voice/repositories/voice_repository.dart';
import 'features/voice/providers/voice_provider.dart';
import 'features/care/providers/care_provider.dart';
import 'features/care/repositories/care_repository.dart';
import 'features/care/screens/family_home_screen.dart';
import 'features/care/screens/elder_home_screen.dart';
import 'features/health/repositories/health_repository.dart';
import 'features/session/services/session_manager.dart';
import 'features/agent/repositories/agent_repository.dart';
import 'features/agent/providers/agent_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final sessionManager = SessionManager(prefs);
  final endpointConfig = ServerEndpointConfig(prefs);

  runApp(
    AppBootstrap(
      sessionManager: sessionManager,
      endpointConfig: endpointConfig,
    ),
  );
}

class AppBootstrap extends StatelessWidget {
  final SessionManager sessionManager;
  final ServerEndpointConfig endpointConfig;

  const AppBootstrap({
    super.key,
    required this.sessionManager,
    required this.endpointConfig,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider.value(value: sessionManager),
        ChangeNotifierProvider.value(value: endpointConfig),
        ProxyProvider2<SessionManager, ServerEndpointConfig, ApiClient>(
          update: (_, session, endpoint, __) => ApiClient(
            endpointConfig: endpoint,
            sessionManager: session,
            onUnauthorized: () {
              // 处理 401 全局重定向
            },
          ),
        ),
        ProxyProvider<ApiClient, AuthRepository>(
          update: (_, client, __) => AuthRepository(client),
        ),
        ProxyProvider<ApiClient, CareRepository>(
          update: (_, client, __) => CareRepository(client),
        ),
        ProxyProvider2<ApiClient, ServerEndpointConfig, AlarmRepository>(
          update: (_, client, endpoint, __) => AlarmRepository(
            client,
            endpointConfig: endpoint,
          ),
        ),
        ProxyProvider<ApiClient, VoiceRepository>(
          update: (_, client, __) => VoiceRepository(client),
        ),
        ProxyProvider2<ApiClient, ServerEndpointConfig, HealthRepository>(
          update: (_, client, endpoint, __) => HealthRepository(
            client,
            endpointConfig: endpoint,
          ),
        ),
        ProxyProvider<ApiClient, AgentRepository>(
          update: (_, client, __) => AgentRepository(client),
        ),
        ChangeNotifierProxyProvider2<AuthRepository, SessionManager, AuthProvider>(
          create: (context) => AuthProvider(
            context.read<AuthRepository>(),
            context.read<SessionManager>(),
          ),
          update: (context, authRepo, session, prevAuth) =>
              prevAuth ?? AuthProvider(authRepo, session),
        ),
        ChangeNotifierProxyProvider<CareRepository, CareProvider>(
          create: (context) => CareProvider(context.read<CareRepository>()),
          update: (context, repo, prev) => prev ?? CareProvider(repo),
        ),
        ChangeNotifierProxyProvider<AlarmRepository, AlarmProvider>(
          create: (context) => AlarmProvider(context.read<AlarmRepository>()),
          update: (context, repo, prev) => prev ?? AlarmProvider(repo),
        ),
        ChangeNotifierProxyProvider<VoiceRepository, VoiceProvider>(
          create: (context) => VoiceProvider(context.read<VoiceRepository>()),
          update: (context, repo, prev) => prev ?? VoiceProvider(repo),
        ),
        ChangeNotifierProxyProvider<AgentRepository, AgentProvider>(
          create: (context) => AgentProvider(context.read<AgentRepository>()),
          update: (context, repo, prev) => prev ?? AgentProvider(repo),
        ),
      ],
      child: const AiHealthApp(),
    );
  }
}

class AiHealthApp extends StatefulWidget {
  const AiHealthApp({super.key});

  @override
  State<AiHealthApp> createState() => _AiHealthAppState();
}

class _AiHealthAppState extends State<AiHealthApp> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => context.read<AuthProvider>().checkSession());
  }

  @override
  Widget build(BuildContext context) {
    final authStatus = context.watch<AuthProvider>().status;

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AIoT Health',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFFF875A),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: GlobalAlarmListener(
        child: _buildHome(context, authStatus),
      ),
    );
  }

  Widget _buildHome(BuildContext context, AuthStatus status) {
    if (status == AuthStatus.initial) {
      return const Scaffold(
        backgroundColor: Color(0xFF08161B),
        body: Center(child: CircularProgressIndicator(color: Color(0xFFFF875A))),
      );
    }

    if (status == AuthStatus.authenticated) {
      final user = context.read<AuthProvider>().user;
      if (user?.role == 'elder') {
        return const ElderHomeScreen();
      }
      return const FamilyHomeScreen();
    }

    return const LoginScreen();
  }
}
