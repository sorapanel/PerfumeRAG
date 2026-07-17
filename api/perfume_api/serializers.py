"""リクエスト/レスポンスのシリアライザー。"""

from rest_framework import serializers


class QueryRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500)
    top_k = serializers.IntegerField(min_value=1, max_value=20, default=5)
    filters = serializers.DictField(child=serializers.CharField(), required=False, default=None)


class SourceSerializer(serializers.Serializer):
    id = serializers.CharField()
    document = serializers.CharField()
    metadata = serializers.DictField()
    distance = serializers.FloatField()


class QueryResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    sources = SourceSerializer(many=True)
    query = serializers.CharField()
