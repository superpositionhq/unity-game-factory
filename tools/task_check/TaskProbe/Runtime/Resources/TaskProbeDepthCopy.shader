// The drawn renderer's depth read: a depth texture's raw values copied into a float texture the CPU can read back
// (a depth-format texture can't be read back directly).
Shader "Hidden/TaskProbe/DepthCopy"
{
    Properties { _MainTex ("Depth", 2D) = "black" {} }
    SubShader
    {
        Cull Off ZWrite Off ZTest Always
        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag
            #include "UnityCG.cginc"
            UNITY_DECLARE_DEPTH_TEXTURE(_MainTex);
            float4 frag(v2f_img i) : SV_Target
            {
                float d = SAMPLE_DEPTH_TEXTURE(_MainTex, i.uv);
                return float4(d, d, d, 1);
            }
            ENDCG
        }
    }
}
