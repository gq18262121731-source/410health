import '../../../core/network/api_client.dart';
import '../models/care_profile_model.dart';

class CareRepository {
  final ApiClient _apiClient;

  CareRepository(this._apiClient);

  Future<CareAccessProfile> getAccessProfile() async {
    final response = await _apiClient.get('/care/access-profile/me');
    return CareAccessProfile.fromJson(response.data);
  }
}
