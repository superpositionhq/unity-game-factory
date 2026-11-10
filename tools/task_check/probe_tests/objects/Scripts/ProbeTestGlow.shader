// A glowing shader with no standard interface (no _EmissionColor, no _BaseColor, not named unlit): lit/glow must read
// it as rendered.
Shader "Custom/ProbeTestGlow"
{
    Properties { _Glow ("Glow", Color) = (3, 2, 1, 1) }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            CBUFFER_START(UnityPerMaterial)
            half4 _Glow;
            CBUFFER_END
            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; };
            Varyings vert(Attributes i) { Varyings o; o.positionCS = TransformObjectToHClip(i.positionOS.xyz); return o; }
            half4 frag(Varyings i) : SV_Target { return _Glow; }
            ENDHLSL
        }
    }
}
