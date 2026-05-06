import '../../../core/network/api_client.dart';
import '../../session/models/user_model.dart';
import '../models/register_models.dart';

class AuthRepository {
  final ApiClient _apiClient;

  AuthRepository(this._apiClient);

  Future<LoginResponse> login(String username, String password) async {
    final response = await _apiClient.post('auth/login', data: {
      'username': username,
      'password': password,
    });
    return LoginResponse.fromJson(response.data);
  }

  Future<SessionUser> getMe() async {
    final response = await _apiClient.get('auth/me');
    return SessionUser.fromJson(response.data);
  }

  Future<void> registerMobileDevice(Map<String, dynamic> payload) async {
    await _apiClient.post('auth/mobile-devices', data: payload);
  }

  Future<void> revokeMobileDevice(String installationId) async {
    await _apiClient.delete('auth/mobile-devices/$installationId');
  }

  Future<RegisterResponse> registerElder(ElderRegisterRequest request) async {
    final response = await _apiClient.post('auth/register/elder', data: request.toJson());
    return RegisterResponse.fromJson(response.data);
  }

  Future<RegisterResponse> registerFamily(FamilyRegisterRequest request) async {
    final response = await _apiClient.post('auth/register/family', data: request.toJson());
    return RegisterResponse.fromJson(response.data);
  }

  Future<RegisterResponse> registerCommunity(CommunityRegisterRequest request) async {
    final response = await _apiClient.post('auth/register/community-staff', data: request.toJson());
    return RegisterResponse.fromJson(response.data);
  }
}
