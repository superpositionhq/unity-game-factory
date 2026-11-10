// The asset family's own shader: a Vector, an Integer and a Color property that URP never rewrites on import.
Shader "ProbeTests/AssetParams"
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
