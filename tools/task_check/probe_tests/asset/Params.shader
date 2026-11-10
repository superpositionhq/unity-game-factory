Shader "AssetTest/Params"
{
    Properties
    {
        _Wind ("Wind", Vector) = (0, 0, 0, 0)
        _Steps ("Steps", Integer) = 3
        _Tint ("Tint", Color) = (1, 1, 1, 1)
    }
    SubShader
    {
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            float4 _Tint;
            float4 vert(float4 p : POSITION) : SV_POSITION { return p; }
            float4 frag() : SV_Target { return _Tint; }
            ENDHLSL
        }
    }
}
